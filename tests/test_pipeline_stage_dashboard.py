"""Dashboard test for persisted production-stage status visibility."""
from __future__ import annotations

from fastapi.testclient import TestClient

from upsc_studio.agents.runtime import AgentTaskStore, TaskSpec
from upsc_studio.db.database import init_db
from upsc_studio.web.app import create_app


def test_project_detail_exposes_latest_persisted_pipeline_stage(tmp_path) -> None:
    db_path = tmp_path / "pipeline-status.db"
    projects_root = tmp_path / "projects"
    app = create_app(db_path=db_path, projects_root=projects_root)
    client = TestClient(app)
    created = client.post(
        "/api/projects",
        json={"name": "Stage visibility", "chapter_title": "Federalism"},
    )
    assert created.status_code == 200
    project_id = created.json()["id"]

    conn = init_db(db_path)
    store = AgentTaskStore(conn)
    workflow_id = f"chapter-pipeline:{project_id}"
    task_id = store.enqueue(
        workflow_id,
        TaskSpec(
            "ingestion",
            "PIPELINE_INGESTION",
            "pipeline_ingestion",
            payload={"fingerprint": "test"},
            max_retries=0,
        ),
    )
    store.transition(task_id, "RUNNING")
    store.transition(task_id, "COMPLETED", output={"status": "COMPLETED"})
    conn.close()

    detail = client.get(f"/api/projects/{project_id}")
    assert detail.status_code == 200
    stages = detail.json()["pipeline_tasks"]
    assert len(stages) == 1
    assert stages[0]["handler"] == "pipeline_ingestion"
    assert stages[0]["stage_name"] == "1. Input ingestion"
    assert stages[0]["status"] == "COMPLETED"
    assert stages[0]["attempts"] == 1
