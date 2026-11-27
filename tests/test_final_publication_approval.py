"""Ensure rendering/automated gates never substitute for final human release approval."""
from __future__ import annotations

import json
from pathlib import Path

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, ProjectStatus, SceneSpec
from upsc_studio.pipeline.staged import StagedChapterPipeline
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.qa.auditor import QAAuditor
from upsc_studio.qa.ten_gates import TenGateAuditor


def test_all_automated_checks_without_publication_approval_stay_needs_review(
    tmp_path: Path, monkeypatch
) -> None:
    conn = init_db(tmp_path / "approval.db")
    manager = ProjectManager(conn, tmp_path / "projects")
    project = manager.create_project(
        ProjectCreate(name="Release approval", chapter_title="Federalism")
    )
    root = Path(project.root_dir)
    scene = SceneSpec(
        scene_id="SCN_01",
        section_id="SEC_01",
        section_title="Introduction",
        learning_objective="Introduce the topic",
        narration_text="Evidence-backed narration",
        estimated_duration_sec=6.0,
        visual_category="Title Card",
        primary_asset=str(root / "graphics" / "scene.png"),
        on_screen_title="Federalism",
    )
    storyboard = root / "storyboard" / "storyboard.json"
    storyboard.parent.mkdir(parents=True, exist_ok=True)
    storyboard.write_text(json.dumps([scene.model_dump(mode="json")]), encoding="utf-8")
    final_video = root / "render" / "final" / "final_video.mp4"
    final_video.parent.mkdir(parents=True, exist_ok=True)
    final_video.write_bytes(b"test video")
    report_path = root / "workflow" / "stages" / "render.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps({"render_manifest": {"final_video": str(final_video)}}),
        encoding="utf-8",
    )
    paths = StagedChapterPipeline(conn, tmp_path / "projects")._paths(root)

    monkeypatch.setattr(
        QAAuditor,
        "run_all_checks",
        lambda self, project_id: {
            "academic": {"status": "PASSED"},
            "rights": {"status": "PASSED"},
            "media": {"status": "PASSED"},
            "publication": {"status": "PENDING"},
        },
    )
    monkeypatch.setattr(
        TenGateAuditor,
        "run_ten_gates",
        lambda self, project_id, scenes, video: {
            "all_gates_passed": True,
            "failed_gates": [],
            "pending_gates": [],
            "ready_for_publication": "PENDING",
        },
    )

    result = StagedChapterPipeline(conn, tmp_path / "projects")._stage_qa(
        project.id, root, paths
    )
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["pipeline_status"] == ProjectStatus.NEEDS_REVIEW.value
    assert manager.get_project(project.id).status == ProjectStatus.NEEDS_REVIEW
