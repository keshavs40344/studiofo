"""Upload limits and extension validation tests for the local dashboard."""
from __future__ import annotations

from fastapi.testclient import TestClient

from upsc_studio.web.app import create_app


def test_run_route_rejects_unsupported_upload_extension(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "uploads.db",
        projects_root=tmp_path / "uploads_projects",
    )
    client = TestClient(app)
    created = client.post(
        "/api/projects",
        json={"name": "Upload validation", "chapter_title": "Test topic"},
    )
    project_id = created.json()["id"]
    response = client.post(
        f"/api/projects/{project_id}/run",
        files={"notes_file": ("payload.exe", b"not a document", "application/octet-stream")},
        data={"typed_notes": ""},
    )
    assert response.status_code == 415


def test_run_route_rejects_pasted_notes_over_limit(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "notes-size.db",
        projects_root=tmp_path / "notes_projects",
    )
    client = TestClient(app)
    created = client.post(
        "/api/projects",
        json={"name": "Notes size", "chapter_title": "Test topic"},
    )
    project_id = created.json()["id"]
    response = client.post(
        f"/api/projects/{project_id}/run",
        data={"typed_notes": "x" * (512 * 1024 + 1)},
    )
    assert response.status_code == 413
