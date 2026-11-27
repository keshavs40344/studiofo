"""Per-run publishing consent, QA fingerprint and duplicate-upload tests."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import SceneSpec
from upsc_studio.qa.ten_gates import TenGateAuditor
from upsc_studio.web import app as web_module
from upsc_studio.web.app import create_app


def _prepare_approved_project(tmp_path: Path):
    db_path = tmp_path / "publish.db"
    projects_root = tmp_path / "projects"
    app = create_app(db_path=db_path, projects_root=projects_root)
    client = TestClient(app)
    created = client.post(
        "/api/projects",
        json={"name": "Publish test", "chapter_title": "Federalism"},
    )
    project_id = created.json()["id"]
    root = Path(client.get(f"/api/projects/{project_id}").json()["project"]["root_dir"])
    scene = SceneSpec(
        scene_id="SCN_01",
        section_id="SEC_01",
        section_title="Definition",
        learning_objective="Explain federalism",
        narration_text="Federalism distributes constitutional powers.",
        claim_ids=["clm_1"],
        estimated_duration_sec=18,
        visual_category="Diagram",
        primary_asset=None,
        on_screen_title="Federalism",
    )
    storyboard = root / "storyboard" / "storyboard.json"
    storyboard.parent.mkdir(parents=True, exist_ok=True)
    storyboard.write_text(json.dumps([scene.model_dump(mode="json")]), encoding="utf-8")
    final_video = root / "render" / "final" / "final_video.mp4"
    final_video.parent.mkdir(parents=True, exist_ok=True)
    final_video.write_bytes(b"approved-video-fixture")
    conn = init_db(db_path)
    conn.execute("UPDATE projects SET status = 'APPROVED' WHERE id = ?", (project_id,))
    conn.commit()
    fingerprint = TenGateAuditor(conn, root).review_fingerprint(project_id, [scene], final_video)
    review = root / "qa" / "manual_review.json"
    review.parent.mkdir(parents=True, exist_ok=True)
    review.write_text(
        json.dumps({"reviewer": "Creator", "artifact_fingerprint": fingerprint,
                    "checks": {"final_playback_inspection": True}}),
        encoding="utf-8",
    )
    conn.close()
    return client, project_id, root


def test_youtube_publish_requires_explicit_per_run_confirmation(tmp_path: Path) -> None:
    client, project_id, _ = _prepare_approved_project(tmp_path)
    response = client.post(
        f"/api/projects/{project_id}/publish",
        json={"privacy_status": "private", "approver": "Creator", "confirm_publish": False},
    )
    assert response.status_code == 409
    assert "per-run publication confirmation" in response.json()["detail"]


def test_successful_youtube_upload_is_receipted_and_not_repeated(
    tmp_path: Path, monkeypatch
) -> None:
    client, project_id, root = _prepare_approved_project(tmp_path)
    monkeypatch.setattr(
        web_module.TenGateAuditor,
        "run_ten_gates",
        lambda self, project_id, scenes, video, human_approved_by=None: {
            "ready_for_publication": "PASSED",
            "gates": {f"GATE_{n}": "PASSED" for n in range(10)},
        },
    )
    calls = []

    def fake_upload(self, video_path, metadata, qa_passed, privacy_status, human_approved_by):
        calls.append((privacy_status, human_approved_by, qa_passed))
        return {"status": "UPLOADED", "video_id": "youtube-test-id",
                "privacy_status": privacy_status}

    monkeypatch.setattr(web_module.YouTubePublisher, "upload_video", fake_upload)
    payload = {
        "privacy_status": "private",
        "approver": "Creator",
        "confirm_publish": True,
    }
    first = client.post(f"/api/projects/{project_id}/publish", json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["upload_result"]["status"] == "UPLOADED"
    assert Path(root / "publishing" / "youtube_upload_receipt.json").is_file()

    second = client.post(f"/api/projects/{project_id}/publish", json=payload)
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "ALREADY_UPLOADED"
    assert len(calls) == 1
    assert calls[0] == ("private", "Creator", True)


def test_youtube_publish_rejects_changed_artifacts_after_manual_review(tmp_path: Path) -> None:
    client, project_id, root = _prepare_approved_project(tmp_path)
    with (root / "render" / "final" / "final_video.mp4").open("ab") as handle:
        handle.write(b"changed-after-review")
    response = client.post(
        f"/api/projects/{project_id}/publish",
        json={"privacy_status": "private", "approver": "Creator", "confirm_publish": True},
    )
    assert response.status_code == 409
    assert "Manual review is stale" in response.json()["detail"]
