"""Human review gating and stale-review invalidation tests."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, SceneSpec
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.qa.completeness_audit import CompletenessAuditor
from upsc_studio.qa.ten_gates import TenGateAuditor
from upsc_studio.web.app import create_app


def _make_reviewable_project(tmp_path: Path):
    conn = init_db(tmp_path / "review.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(name="Manual review", chapter_title="Sample topic")
    )
    root = Path(project.root_dir)
    for relative, content in {
        "teaching/script_hinglish.md": "# Script\nA source-backed lesson.",
        "teaching/teaching_outline.md": "# Outline\nSection 1",
        "subtitles/subtitles.srt": "1\n00:00:00,000 --> 00:00:01,000\nHello\n",
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    asset = root / "graphics" / "scene.txt"
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_text("visual placeholder", encoding="utf-8")
    video = root / "render" / "final" / "final_video.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"fake test video")
    scene = SceneSpec(
        scene_id="SCN_01",
        section_id="SEC_01",
        section_title="Introduction",
        learning_objective="Introduce the topic",
        narration_text="A source-backed lesson.",
        estimated_duration_sec=6.0,
        visual_category="Title Card",
        primary_asset=str(asset),
        on_screen_title="Sample topic",
    )
    return conn, project, root, scene, video


def test_manual_quality_gates_require_current_explicit_review(
    tmp_path: Path, monkeypatch
) -> None:
    conn, project, root, scene, video = _make_reviewable_project(tmp_path)
    monkeypatch.setattr(
        CompletenessAuditor,
        "audit_video",
        lambda self, scenes, final_mp4: {
            "black_frame_segments_detected": 0,
            "scenes_audited": len(scenes),
        },
    )
    auditor = TenGateAuditor(conn, root)

    before = auditor.run_ten_gates(project.id, [scene], video)
    assert before["gates"]["E_TEACHING_CLARITY"] == "PENDING"
    assert before["gates"]["F_VISUAL_RELEVANCE"] == "PENDING"
    assert before["gates"]["G_VOICE_SUBTITLE_ALIGNMENT"] == "PENDING"
    assert before["gates"]["J_FINAL_PLAYBACK_INSPECTION"] == "PENDING"

    review = {
        "reviewer": "Creator",
        "artifact_fingerprint": auditor.review_fingerprint(project.id, [scene], video),
        "checks": {
            "teaching_clarity": True,
            "visual_relevance": True,
            "voice_subtitle_alignment": True,
            "final_playback_inspection": True,
        },
        "reviewed_at": "2026-11-27T00:00:00+00:00",
    }
    review_path = root / "qa" / "manual_review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")

    after = auditor.run_ten_gates(project.id, [scene], video)
    assert after["gate_details"]["MANUAL_REVIEW"]["review_is_current"] is True
    assert after["gates"]["E_TEACHING_CLARITY"] == "PASSED"
    assert after["gates"]["F_VISUAL_RELEVANCE"] == "PASSED"
    assert after["gates"]["G_VOICE_SUBTITLE_ALIGNMENT"] == "PASSED"
    assert after["gates"]["J_FINAL_PLAYBACK_INSPECTION"] == "PASSED"

    # Editing a reviewed artifact invalidates all manual decisions.
    (root / "teaching" / "script_hinglish.md").write_text(
        "# Script\nChanged after review.", encoding="utf-8"
    )
    stale = auditor.run_ten_gates(project.id, [scene], video)
    assert stale["gate_details"]["MANUAL_REVIEW"]["review_is_current"] is False
    assert stale["gates"]["E_TEACHING_CLARITY"] == "PENDING"
    assert stale["gates"]["F_VISUAL_RELEVANCE"] == "PENDING"
    assert stale["gates"]["G_VOICE_SUBTITLE_ALIGNMENT"] == "PENDING"
    assert stale["gates"]["J_FINAL_PLAYBACK_INSPECTION"] == "PENDING"


def test_dashboard_persists_manual_review_and_returns_it_on_project_detail(tmp_path: Path) -> None:
    app = create_app(
        db_path=tmp_path / "dashboard.db",
        projects_root=tmp_path / "dashboard_projects",
    )
    client = TestClient(app)
    created = client.post(
        "/api/projects",
        json={"name": "Review API", "chapter_title": "Public Finance"},
    )
    assert created.status_code == 200
    project_id = created.json()["id"]

    saved = client.post(
        f"/api/projects/{project_id}/review",
        json={
            "reviewer": "Creator",
            "teaching_clarity": True,
            "visual_relevance": False,
            "voice_subtitle_alignment": False,
            "final_playback_inspection": False,
            "notes": "Only the script has been checked so far.",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["manual_review"]["checks"]["teaching_clarity"] is True
    assert saved.json()["manual_review"]["checks"]["final_playback_inspection"] is False
    assert saved.json()["manual_review"]["artifact_fingerprint"]

    detail = client.get(f"/api/projects/{project_id}")
    assert detail.status_code == 200
    assert detail.json()["manual_review"]["reviewer"] == "Creator"
