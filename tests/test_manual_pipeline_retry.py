"""Reviewed retry API resets only the failed stage and dependent work."""
from __future__ import annotations

from fastapi.testclient import TestClient

from upsc_studio.agents.runtime import AgentTaskStore, DependencyScheduler, TaskSpec
from upsc_studio.db.database import init_db
from upsc_studio.web.app import create_app


def _completed(payload):
    return {"status": "COMPLETED"}


def _fail(payload):
    raise RuntimeError("deliberate stage failure for retry test")


def test_manual_retry_preserves_successful_upstream_and_reopens_outer_workflow(tmp_path) -> None:
    db_path = tmp_path / "retry.db"
    app = create_app(db_path=db_path, projects_root=tmp_path / "projects")
    client = TestClient(app)
    created = client.post(
        "/api/projects",
        json={"name": "Retry project", "chapter_title": "Federalism"},
    )
    project_id = created.json()["id"]

    conn = init_db(db_path)
    store = AgentTaskStore(conn)
    stage_order = [
        "pipeline_ingestion",
        "pipeline_academic",
        "pipeline_teaching",
        "pipeline_visuals",
        "pipeline_voice",
        "pipeline_render",
        "pipeline_qa",
    ]
    stage_specs = [
        TaskSpec("ingestion", "PIPELINE_INGESTION", "pipeline_ingestion"),
        TaskSpec("academic", "PIPELINE_ACADEMIC", "pipeline_academic", depends_on=("ingestion",)),
        TaskSpec("teaching", "PIPELINE_TEACHING", "pipeline_teaching", depends_on=("academic",)),
        TaskSpec("visuals", "PIPELINE_VISUALS", "pipeline_visuals", depends_on=("teaching",)),
        TaskSpec("voice", "PIPELINE_VOICE", "pipeline_voice", depends_on=("visuals",)),
        TaskSpec("render", "PIPELINE_RENDER", "pipeline_render", depends_on=("voice",)),
        TaskSpec("qa", "PIPELINE_QA", "pipeline_qa", depends_on=("render",)),
    ]
    inner_id = f"chapter-pipeline:{project_id}"
    stage_handlers = {handler: _completed for handler in stage_order}
    stage_handlers["pipeline_academic"] = _fail
    stage_run = DependencyScheduler(store, stage_handlers).run(inner_id, stage_specs)
    assert stage_run["status"] == "FAILED"

    outer_id = f"production:{project_id}:testfingerprint"
    outer_specs = [
        TaskSpec("preflight", "SUPERVISOR", "preflight"),
        TaskSpec("production", "SUPERVISOR", "chapter_pipeline", depends_on=("preflight",)),
        TaskSpec("editorial", "SUPERVISOR", "editorial_packaging", depends_on=("production",)),
        TaskSpec("publish", "SUPERVISOR", "gated_private_publish", depends_on=("editorial",)),
    ]
    DependencyScheduler(
        store,
        {
            "preflight": _completed,
            "chapter_pipeline": _completed,
            "editorial_packaging": _completed,
            "gated_private_publish": _completed,
        },
    ).run(outer_id, outer_specs)
    conn.close()

    response = client.post(
        f"/api/projects/{project_id}/retry",
        json={
            "reviewer": "Creator",
            "reason": "Fixed the documented parser failure.",
            "partial_outputs_inspected": True,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "RETRY_PREPARED"
    assert result["start_stage"] == "pipeline_academic"

    check_conn = init_db(db_path)
    check_store = AgentTaskStore(check_conn)
    inner = check_store.list_workflow(inner_id)
    latest = {}
    for row in inner:
        latest[row["handler"]] = row["status"]
    assert latest["pipeline_ingestion"] == "COMPLETED"
    assert latest["pipeline_academic"] == "PENDING"
    assert latest["pipeline_teaching"] == "PENDING"
    assert latest["pipeline_visuals"] == "PENDING"

    outer = check_store.list_workflow(outer_id)
    outer_latest = {}
    for row in outer:
        outer_latest[row["handler"]] = row["status"]
    assert outer_latest["preflight"] == "COMPLETED"
    assert outer_latest["chapter_pipeline"] == "PENDING"
    assert outer_latest["editorial_packaging"] == "PENDING"
    assert outer_latest["gated_private_publish"] == "PENDING"
    check_conn.close()


def test_manual_retry_requires_reviewer_and_inspection_confirmation(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "retry-guard.db",
        projects_root=tmp_path / "retry-guard-projects",
    )
    client = TestClient(app)
    created = client.post(
        "/api/projects",
        json={"name": "Retry guard", "chapter_title": "Federalism"},
    )
    project_id = created.json()["id"]
    response = client.post(
        f"/api/projects/{project_id}/retry",
        json={
            "reviewer": "Creator",
            "reason": "Retry after failure",
            "partial_outputs_inspected": False,
        },
    )
    assert response.status_code == 409
