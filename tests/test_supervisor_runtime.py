"""Regression tests for persistent supervisor execution and publication approval."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from upsc_studio.agents import supervisor as supervisor_module
from upsc_studio.agents.supervisor import ExecutiveProducer
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, SceneSpec
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.research.verifier import EvidenceEngine


def _scene() -> SceneSpec:
    return SceneSpec(
        scene_id="SCN_02",
        section_id="SEC_02",
        section_title="How the mechanism works",
        learning_objective="Explain the mechanism step by step",
        narration_text="The mechanism has defined stages and a measurable outcome.",
        estimated_duration_sec=12.0,
        visual_category="Flowchart",
        on_screen_title="Mechanism",
        on_screen_bullets=["Stage one", "Stage two"],
        source_citations=["Test source"],
    )


def test_supervisor_persists_pipeline_and_reuses_it_when_only_publish_approval_changes(
    tmp_path: Path, monkeypatch
) -> None:
    conn = init_db(tmp_path / "studio.db")
    projects_root = tmp_path / "projects"
    manager = ProjectManager(conn, projects_root)
    project = manager.create_project(
        ProjectCreate(name="Runtime Integration", chapter_title="A test chapter")
    )
    project_dir = Path(project.root_dir)
    storyboard = project_dir / "storyboard" / "storyboard.json"
    storyboard.write_text(
        json.dumps([_scene().model_dump(mode="json")], ensure_ascii=False),
        encoding="utf-8",
    )
    final_video = project_dir / "video" / "final" / "final.mp4"
    final_video.parent.mkdir(parents=True, exist_ok=True)
    final_video.write_bytes(b"test-video")

    pipeline_calls = {"count": 0}
    publisher_calls = {"count": 0}

    class FakePipeline:
        def __init__(self, _conn, _projects_root):
            pass

        def run_staged(self, **kwargs):
            pipeline_calls["count"] += 1
            return {
                "status": "APPROVED",
                "project_id": project.id,
                "chapter_map": {"primary_papers": ["GS-II"]},
                "publishing_package": {"video_title": "Test chapter"},
                "render_manifest": {"final_video": str(final_video)},
                "audio_report": {"duration_sec": 12.0},
                "qa": {
                    "academic": {"status": "PASSED"},
                    "rights": {"status": "PASSED"},
                    "media": {"status": "PASSED"},
                },
                "ten_gates": {
                    "all_gates_passed": True, "failed_gates": [], "pending_gates": []
                },
                "recording_script": None,
                "scenes_count": 1,
            }

    class FakePublisher:
        def __init__(self, token_path=None):
            self.token_path = token_path

        def upload_video(self, video_path, metadata, qa_passed, privacy_status):
            publisher_calls["count"] += 1
            assert Path(video_path).is_file()
            assert qa_passed is True
            assert privacy_status == "private"
            assert metadata["video_title"] == "Test chapter"
            return {
                "status": "UPLOADED",
                "video_id": "test-video-id",
                "privacy_status": "private",
            }

    monkeypatch.setattr(supervisor_module, "StagedChapterPipeline", FakePipeline)
    monkeypatch.setattr(supervisor_module, "YouTubePublisher", FakePublisher)

    producer = ExecutiveProducer(conn, projects_root)
    first = producer.run_autonomous_factory(
        project.id,
        typed_notes="PRIVATE CONTENT MUST NOT BE COPIED INTO TASK PAYLOAD",
        ai_narration=False,
    )

    assert first["workflow"]["status"] == "COMPLETED"
    assert first["workflow"]["task_count"] == 4
    assert first["youtube_publish"]["status"] == "BLOCKED_AWAITING_EXPLICIT_PUBLISH_APPROVAL"
    assert publisher_calls["count"] == 0
    assert first["agent_states"]["AGENT_01"]["status"] == "COMPLETED"
    assert first["agent_states"]["AGENT_20"]["status"] == "COMPLETED"
    assert first["agent_states"]["AGENT_02"]["status"] == "REGISTERED"
    assert first["agent_states"]["AGENT_23"]["status"] == "BLOCKED"

    stored_payloads = [
        row[0]
        for row in conn.execute("SELECT payload_json FROM agent_tasks").fetchall()
    ]
    assert all("PRIVATE CONTENT MUST NOT" not in payload for payload in stored_payloads)

    # Changing publication approval must not enqueue a second render or rerun research.
    second = producer.run_autonomous_factory(
        project.id,
        typed_notes="PRIVATE CONTENT MUST NOT BE COPIED INTO TASK PAYLOAD",
        ai_narration=False,
        allow_youtube_upload=True,
        human_publish_approval=True,
    )
    assert second["workflow"]["status"] == "COMPLETED"
    assert second["status"] == "APPROVED"
    assert second["youtube_publish"]["status"] == "UPLOADED"
    assert second["agent_states"]["AGENT_23"]["status"] == "COMPLETED"
    assert pipeline_calls["count"] == 1
    assert publisher_calls["count"] == 1

    task_rows = conn.execute(
        "SELECT handler, status FROM agent_tasks ORDER BY created_at, task_id"
    ).fetchall()
    assert sum(row[0] == "chapter_pipeline" for row in task_rows) == 1
    assert sum(row[0] == "editorial_packaging" for row in task_rows) == 1
    assert sum(row[0] == "gated_private_publish" for row in task_rows) == 2


def test_supervisor_does_not_retry_failed_non_idempotent_production(
    tmp_path: Path, monkeypatch
) -> None:
    conn = init_db(tmp_path / "failed.db")
    projects_root = tmp_path / "projects"
    project = ProjectManager(conn, projects_root).create_project(
        ProjectCreate(name="Failure handling", chapter_title="Failure test")
    )
    calls = {"count": 0}

    class FailingPipeline:
        def __init__(self, _conn, _projects_root):
            pass

        def run_staged(self, **kwargs):
            calls["count"] += 1
            raise RuntimeError("injected permanent production failure")

    monkeypatch.setattr(supervisor_module, "StagedChapterPipeline", FailingPipeline)
    result = ExecutiveProducer(conn, projects_root).run_autonomous_factory(
        project.id, ai_narration=False
    )

    assert calls["count"] == 1
    assert result["workflow"]["status"] == "REVIEW_REQUIRED"
    # Runtime quarantines the failed production agent as BLOCKED after the
    # non-idempotent workflow is marked REVIEW_REQUIRED; it must not be retried.
    assert result["agent_states"]["AGENT_01"]["status"] == "BLOCKED"
    assert result["agent_states"]["AGENT_02"]["status"] == "REGISTERED"
    statuses = {
        row[0]: row[1]
        for row in conn.execute("SELECT handler, status FROM agent_tasks").fetchall()
    }
    assert statuses["chapter_pipeline"] == "FAILED"
    assert statuses["editorial_packaging"] == "BLOCKED"
    assert statuses["gated_private_publish"] == "BLOCKED"

def test_supervisor_workflow_identity_changes_when_external_research_changes(
    tmp_path: Path, monkeypatch
) -> None:
    conn = init_db(tmp_path / "evidence-fingerprint.db")
    projects_root = tmp_path / "projects"
    project = ProjectManager(conn, projects_root).create_project(
        ProjectCreate(
            name="Evidence fingerprint",
            chapter_title="Energy transition",
            content_category="deep_dive",
        )
    )
    project_dir = Path(project.root_dir)
    storyboard = project_dir / "storyboard" / "storyboard.json"
    storyboard.write_text(
        json.dumps([_scene().model_dump(mode="json")], ensure_ascii=False),
        encoding="utf-8",
    )

    calls = {"pipeline": 0}

    class FakePipeline:
        def __init__(self, _conn, _projects_root):
            pass

        def run_staged(self, **kwargs):
            calls["pipeline"] += 1
            return {
                "status": "WAITING_FOR_VOICE",
                "project_id": project.id,
                "content_category": "deep_dive",
                "chapter_map": {"primary_papers": []},
                "publishing_package": {},
                "render_manifest": None,
                "audio_report": None,
                "qa": {},
                "ten_gates": {},
                "recording_script": None,
                "scenes_count": 1,
            }

    monkeypatch.setattr(supervisor_module, "StagedChapterPipeline", FakePipeline)
    producer = ExecutiveProducer(conn, projects_root)
    first = producer.run_autonomous_factory(project.id, ai_narration=False)
    second = producer.run_autonomous_factory(project.id, ai_narration=False)
    assert first["workflow"]["workflow_id"] == second["workflow"]["workflow_id"]
    assert calls["pipeline"] == 1

    EvidenceEngine(conn, project_dir).add_source(
        project.id, "Energy outlook", "Research institute", "ACADEMIC_PEER_REVIEWED",
        url="https://example.org/energy-outlook",
    )
    third = producer.run_autonomous_factory(project.id, ai_narration=False)
    assert third["workflow"]["workflow_id"] != second["workflow"]["workflow_id"]
    assert calls["pipeline"] == 2
