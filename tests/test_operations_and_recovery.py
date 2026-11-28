"""Comprehensive tests for observable, self-recovering operations system.

Simulates all 10 operational scenarios:
1. Process interruption
2. Database lock
3. Network timeout
4. Missing audio
5. FFmpeg failure
6. Disk space exhaustion
7. Duplicate task submission & duplicate publish prevention
8. Stale approval invalidation
9. Failed dependency propagation
10. Restart after partial completion & checkpoint resumption
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from upsc_studio.agents.runtime import AgentTaskStore, DependencyScheduler, TaskSpec
from upsc_studio.core.errors import (
    ErrorCategory,
    classify_error,
    AcademicQualityError,
    MissingDependencyError,
    ResearchValidationError,
    RightsFailureError,
)
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, ProjectStatus, SceneSpec
from upsc_studio.pipeline.monitoring import RuntimeMonitor
from upsc_studio.pipeline.recovery import RecoveryCoordinator
from upsc_studio.pipeline.staged import StagedChapterPipeline
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.qa.ten_gates import TenGateAuditor
from upsc_studio.web.app import create_app


def test_error_classification_taxonomy() -> None:
    """Verify all 10 error categories are accurately classified and retry policies enforced."""
    # 1. Transient external
    err1 = classify_error(TimeoutError("Connection timed out after 30s"))
    assert err1.category == ErrorCategory.TRANSIENT_EXTERNAL
    assert err1.is_retryable is True
    assert err1.requires_human_review is False

    # 2. Missing dependency
    err2 = classify_error(FileNotFoundError("ffmpeg executable was not found on path"))
    assert err2.category == ErrorCategory.MISSING_DEPENDENCY
    assert err2.is_retryable is False
    assert err2.requires_human_review is True

    # 3. Invalid user input
    err3 = classify_error(ValueError("Invalid date format: 2026-99-99"))
    assert err3.category == ErrorCategory.INVALID_USER_INPUT
    assert err3.is_retryable is False

    # 4. Research validation failure
    err4 = classify_error(ResearchValidationError("Unverified claim contradicts official gazette notification"))
    assert err4.category == ErrorCategory.RESEARCH_VALIDATION_FAILURE
    assert err4.is_retryable is False
    assert err4.requires_human_review is True

    # 5. Academic quality failure
    err5 = classify_error(RuntimeError("Prerequisite gap: Basic structure doctrine omitted from syllabus coverage matrix"))
    assert err5.category == ErrorCategory.ACADEMIC_QUALITY_FAILURE
    assert err5.is_retryable is False

    # 6. Rights failure
    err6 = classify_error(RightsFailureError("Asset rights ledger unverified license for third-party diagram"))
    assert err6.category == ErrorCategory.RIGHTS_FAILURE
    assert err6.is_retryable is False

    # 7. Audio / Video failure
    err7 = classify_error(RuntimeError("Audio quality inspector detected severe clipping > 0.985 in voice recording"))
    assert err7.category == ErrorCategory.AUDIO_VIDEO_FAILURE
    assert err7.is_retryable is False

    # 8. Filesystem failure
    err8 = classify_error(PermissionError("Access denied writing to output directory; disk full"))
    assert err8.category == ErrorCategory.FILESYSTEM_FAILURE
    assert err8.is_retryable is False

    # 9. Database failure (Lock vs Schema)
    lock_err = classify_error(sqlite3.OperationalError("database is locked"))
    assert lock_err.category == ErrorCategory.DATABASE_FAILURE
    assert lock_err.is_retryable is True  # Transient lock is retryable with backoff

    schema_err = classify_error(sqlite3.IntegrityError("FOREIGN KEY constraint failed"))
    assert schema_err.category == ErrorCategory.DATABASE_FAILURE
    assert schema_err.is_retryable is False  # Structural violation requires review

    # 10. Authentication failure
    auth_err = classify_error(RuntimeError("YouTube OAuth client_secrets missing or token expired"))
    assert auth_err.category == ErrorCategory.AUTHENTICATION_FAILURE
    assert auth_err.is_retryable is False


def test_simulated_process_interruption(tmp_path: Path) -> None:
    """Scenario 1: Tasks left in RUNNING from a crash are quarantined to REVIEW_REQUIRED."""
    conn = init_db(tmp_path / "interrupted.db")
    store = AgentTaskStore(conn)
    recovery = RecoveryCoordinator(conn, tmp_path / "projects")

    workflow_id = "chapter-pipeline:proj_crash_01"
    spec = TaskSpec("task_render", "RENDER_AGENT", "pipeline_render")
    tid = store.enqueue(workflow_id, spec)

    # Force task into RUNNING to simulate active execution during power loss/kill
    store.transition(tid, "RUNNING")
    assert store.get(tid)["status"] == "RUNNING"

    # Recovery coordinator detects and quarantines
    interrupted = recovery.detect_interrupted_tasks("proj_crash_01")
    assert len(interrupted) == 1
    assert interrupted[0]["task_id"] == tid

    task_now = store.get(tid)
    assert task_now["status"] == "REVIEW_REQUIRED"
    assert "interrupted" in task_now["error"].lower()
    assert task_now["error_category"] == ErrorCategory.FILESYSTEM_FAILURE.value


def test_simulated_database_lock_and_retry(tmp_path: Path) -> None:
    """Scenario 2: SQLite database lock failure is classified and retried safely."""
    conn = init_db(tmp_path / "dblock.db")
    store = AgentTaskStore(conn)

    attempt_counter = 0

    def lock_handler(payload):
        nonlocal attempt_counter
        attempt_counter += 1
        if attempt_counter == 1:
            raise sqlite3.OperationalError("database is locked")
        return {"status": "COMPLETED", "result": "recovered after lock"}

    workflow_id = "lock_wf"
    spec = TaskSpec("db_task", "DB_AGENT", "lock_handler", max_retries=2, retry_safe=True)
    scheduler = DependencyScheduler(store, {"lock_handler": lock_handler})

    result = scheduler.run(workflow_id, [spec])
    assert result["status"] == "COMPLETED"
    assert attempt_counter == 2  # Retried and succeeded on attempt 2


def test_simulated_network_timeout(tmp_path: Path) -> None:
    """Scenario 3: Network timeout triggers transient retry logic."""
    conn = init_db(tmp_path / "timeout.db")
    store = AgentTaskStore(conn)

    calls = 0

    def network_handler(payload):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("External API request timed out after 10000ms")
        return {"status": "COMPLETED"}

    spec = TaskSpec("api_task", "RESEARCH_AGENT", "net_handler", max_retries=2, retry_safe=True)
    scheduler = DependencyScheduler(store, {"net_handler": network_handler})
    result = scheduler.run("net_wf", [spec])

    assert result["status"] == "COMPLETED"
    assert calls == 2


def test_simulated_missing_audio(tmp_path: Path) -> None:
    """Scenario 4: Voice stage without voice file and without TTS pauses in WAITING_FOR_VOICE."""
    conn = init_db(tmp_path / "missing_audio.db")
    projects_root = tmp_path / "projects"
    project = ProjectManager(conn, projects_root).create_project(
        ProjectCreate(name="Missing Audio Project", chapter_title="Preamble")
    )
    project_dir = Path(project.root_dir)

    pipeline = StagedChapterPipeline(conn, projects_root)
    paths = pipeline._paths(project_dir)

    # Initialize dummy storyboard
    storyboard_dir = project_dir / "storyboard"
    storyboard_dir.mkdir(parents=True, exist_ok=True)
    dummy_scene = SceneSpec(
        scene_id="SCN_01",
        section_id="SEC_01",
        section_title="Introduction",
        learning_objective="Explain preamble",
        narration_text="We the people of India.",
        estimated_duration_sec=8.0,
        visual_category="TextSlide",
        on_screen_title="Preamble",
    )
    (storyboard_dir / "storyboard.json").write_text(
        json.dumps([dummy_scene.model_dump()]), encoding="utf-8"
    )

    # Execute voice stage with no voice and ai_narration=False
    result = pipeline._stage_voice(
        project_id=project.id,
        project_dir=project_dir,
        paths=paths,
        voice_path=None,
        ai_narration=False,
    )

    assert result["status"] == "BLOCKED"
    assert result["pipeline_status"] == ProjectStatus.WAITING_FOR_VOICE.value
    assert "No own-voice recording was supplied" in result["voice_wait_reason"]


def test_simulated_missing_dependency_ffmpeg(tmp_path: Path, monkeypatch) -> None:
    """Scenario 5: Missing FFmpeg fails closed with MISSING_DEPENDENCY."""
    from upsc_studio.video import renderer

    monkeypatch.setattr(renderer, "find_ffmpeg", lambda: None)
    conn = init_db(tmp_path / "ffmpeg.db")
    projects_root = tmp_path / "projects"
    project_dir = tmp_path / "proj_dir"
    video_ren = renderer.VideoRenderer(conn, project_dir)

    with pytest.raises(RuntimeError) as exc_info:
        video_ren.render_project(
            project_id="p1",
            scenes=[],
            narration_wav=tmp_path / "dummy.wav",
        )
    classified = classify_error(exc_info.value)
    assert classified.category in {ErrorCategory.MISSING_DEPENDENCY, ErrorCategory.FILESYSTEM_FAILURE}
    assert classified.is_retryable is False


def test_simulated_disk_space_exhaustion(tmp_path: Path, monkeypatch) -> None:
    """Scenario 6: Low disk space (<1GB) blocks rendering cleanly."""
    from upsc_studio.video import renderer

    monkeypatch.setattr(renderer, "check_disk_space_ok", lambda path, min_free_gb=1.0: (False, 0.45))
    conn = init_db(tmp_path / "disk.db")
    project_dir = tmp_path / "proj_disk"
    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"RIFFdummywav")

    ren = renderer.VideoRenderer(conn, project_dir)
    with pytest.raises(RuntimeError) as exc_info:
        ren.render_project("p_disk", [], dummy_wav)
    assert "Insufficient disk space" in str(exc_info.value)
    classified = classify_error(exc_info.value)
    assert classified.category == ErrorCategory.FILESYSTEM_FAILURE


def test_simulated_duplicate_submission_and_publish_prevention(tmp_path: Path) -> None:
    """Scenario 7: Duplicate task submissions are deduplicated; duplicate publish is blocked."""
    conn = init_db(tmp_path / "dedup.db")
    projects_root = tmp_path / "projects"
    project = ProjectManager(conn, projects_root).create_project(
        ProjectCreate(name="Pub Check", chapter_title="Preamble")
    )
    store = AgentTaskStore(conn)
    recovery = RecoveryCoordinator(conn, projects_root)

    # 1. Deduplication of identical task spec
    spec = TaskSpec("task_1", "AGENT_A", "handler_a", payload={"key": "val"})
    tid1 = store.enqueue("wf_1", spec, input_fingerprint="fp1")
    tid2 = store.enqueue("wf_1", spec, input_fingerprint="fp1")
    assert tid1 == tid2

    # 2. Duplicate publish prevention
    conn.execute(
        """
        INSERT INTO qa_gates (id, project_id, gate_name, status, blocking_issues_json, checked_at)
        VALUES ('g1', ?, 'YOUTUBE_PUBLISHED', 'PASSED', ?, '2026-11-28T00:00:00Z')
        """,
        (project.id, json.dumps({"video_sha256": "abc123sha", "youtube_id": "yt_video_99"})),
    )
    conn.commit()

    allowed, msg = recovery.prevent_duplicate_upload(project.id, "abc123sha")
    assert allowed is False
    assert "Duplicate upload blocked" in msg

    allowed_new, _ = recovery.prevent_duplicate_upload(project.id, "different_sha_456")
    assert allowed_new is True


def test_simulated_stale_approval_invalidation(tmp_path: Path) -> None:
    """Scenario 8: Content drift after human approval invalidates approval to NEEDS_REVIEW."""
    conn = init_db(tmp_path / "stale.db")
    projects_root = tmp_path / "projects"
    project = ProjectManager(conn, projects_root).create_project(
        ProjectCreate(name="Stale Check", chapter_title="Preamble")
    )
    project_dir = Path(project.root_dir)
    recovery = RecoveryCoordinator(conn, projects_root)

    # Mark project APPROVED in DB
    conn.execute("UPDATE projects SET status = 'APPROVED' WHERE id = ?", (project.id,))
    conn.commit()

    # Create dummy manual review with old fingerprint
    qa_dir = project_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    (qa_dir / "manual_review.json").write_text(
        json.dumps({
            "reviewer": "Reviewer A",
            "artifact_fingerprint": "original_fingerprint_hash_111",
            "review_is_current": True,
        }),
        encoding="utf-8",
    )
    (qa_dir / "final_10_gate_report.json").write_text(
        json.dumps({
            "ready_for_publication": "PASSED",
            "gate_details": {"MANUAL_REVIEW": {"review_is_current": True}},
        }),
        encoding="utf-8",
    )

    # Validate approval freshness - should detect drift because storyboard / current fingerprint differs!
    freshness = recovery.validate_approval_freshness(project.id, project_dir)
    assert freshness["approval_valid"] is False
    assert freshness["stale_detected"] is True

    # Verify project status was reset from APPROVED to NEEDS_REVIEW
    current_proj = ProjectManager(conn, projects_root).get_project(project.id)
    assert current_proj.status == ProjectStatus.NEEDS_REVIEW


def test_simulated_failed_dependency_propagation(tmp_path: Path) -> None:
    """Scenario 9: Upstream task failure blocks downstream tasks without corrupting state."""
    conn = init_db(tmp_path / "deps.db")
    store = AgentTaskStore(conn)

    def fail_handler(payload):
        raise AcademicQualityError("Syllabus subtopic coverage gap detected")

    def downstream_handler(payload):
        return {"status": "COMPLETED"}

    specs = [
        TaskSpec("step1", "AGENT_1", "fail_handler"),
        TaskSpec("step2", "AGENT_2", "downstream_handler", depends_on=("step1",)),
    ]
    scheduler = DependencyScheduler(store, {
        "fail_handler": fail_handler,
        "downstream_handler": downstream_handler,
    })

    result = scheduler.run("wf_dep_fail", specs)
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["failed"] == 0
    assert result["review_required"] == 1
    assert result["blocked"] == 1

    tasks = {r["handler"]: r for r in result["tasks"]}
    assert tasks["fail_handler"]["status"] == "REVIEW_REQUIRED"
    assert tasks["fail_handler"]["error_category"] == ErrorCategory.ACADEMIC_QUALITY_FAILURE.value
    assert tasks["downstream_handler"]["status"] == "BLOCKED"


def test_simulated_restart_after_partial_completion(tmp_path: Path) -> None:
    """Scenario 10: Checkpoint resumption skips completed stages and continues from next pending."""
    conn = init_db(tmp_path / "resume.db")
    store = AgentTaskStore(conn)

    executed: list[str] = []

    def handler_1(payload):
        executed.append("handler_1")
        return {"status": "COMPLETED", "data": 123}

    def handler_2(payload):
        executed.append("handler_2")
        return {"status": "COMPLETED", "data": 456}

    specs = [
        TaskSpec("t1", "A1", "handler_1"),
        TaskSpec("t2", "A2", "handler_2", depends_on=("t1",)),
    ]
    scheduler = DependencyScheduler(store, {"handler_1": handler_1, "handler_2": handler_2})

    # Step 1: Execute first task only
    t1_id = store.enqueue("wf_resume", specs[0])
    store.transition(t1_id, "RUNNING")
    res1 = handler_1({})
    store.transition(t1_id, "COMPLETED", output=res1)
    store.checkpoint("wf_resume", "stage_t1", {"checkpoint_num": 1})

    assert executed == ["handler_1"]

    # Step 2: Now run full workflow. handler_1 should be skipped because it is already COMPLETED!
    result = scheduler.run("wf_resume", specs)
    assert result["status"] == "COMPLETED"
    # handler_1 must NOT have been called again
    assert executed == ["handler_1", "handler_2"]


def test_operations_api_endpoints_and_temp_cleanup(tmp_path: Path) -> None:
    """Verify backend API endpoints: /operations, /recover, /cleanup-temp, and /verify-db."""
    db_path = tmp_path / "api_test.db"
    projects_dir = tmp_path / "projects"
    app = create_app(db_path=db_path, projects_root=projects_dir)
    client = TestClient(app)

    # Create project
    create_res = client.post(
        "/api/projects",
        json={"name": "Operations Project", "chapter_title": "Directive Principles"},
    )
    assert create_res.status_code == 200
    project_id = create_res.json()["id"]
    proj_root = Path(create_res.json()["root_dir"])

    # Create dummy temp artifacts
    temp_file = proj_root / "render" / "partial_scene.tmp"
    temp_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file.write_text("temporary bytes for cleanup", encoding="utf-8")
    assert temp_file.is_file()

    # 1. GET /api/projects/{id}/operations
    ops_res = client.get(f"/api/projects/{project_id}/operations")
    assert ops_res.status_code == 200
    ops_data = ops_res.json()
    assert ops_data["project_id"] == project_id
    assert len(ops_data["stages"]) == 7
    assert "system_resources" in ops_data
    assert "database_integrity" in ops_data
    assert ops_data["database_integrity"]["database_ok"] is True

    # 2. POST /api/projects/{id}/cleanup-temp
    clean_res = client.post(f"/api/projects/{project_id}/cleanup-temp")
    assert clean_res.status_code == 200
    clean_data = clean_res.json()
    assert clean_data["count"] == 1
    assert not temp_file.is_file()  # Temp file removed!

    # 3. POST /api/projects/{id}/verify-db
    db_res = client.post(f"/api/projects/{project_id}/verify-db")
    assert db_res.status_code == 200
    assert db_res.json()["database_ok"] is True
    assert db_res.json()["integrity_check"] == "PASSED"

    # 4. POST /api/projects/{id}/recover
    recover_res = client.post(f"/api/projects/{project_id}/recover")
    assert recover_res.status_code == 200
    recover_data = recover_res.json()
    assert recover_data["status"] == "RECOVERED"
    assert "interrupted_tasks_quarantined" in recover_data
    assert "temporary_artifacts_cleaned" in recover_data
