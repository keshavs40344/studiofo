"""Tests for AgentWorkflowRuntime: persistent SQLite DAG, recovery, pause/resume, and idempotency."""

from __future__ import annotations

import sqlite3
from pathlib import Path
import pytest

from upsc_studio.agents.contracts import AgentStatus, SPECIALIST_REGISTRY
from upsc_studio.agents.runtime import AgentWorkflowRuntime
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate
from upsc_studio.projects.manager import ProjectManager


def test_agent_workflow_runtime_creation_and_idempotency(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "test_runtime.db")
    proj_mgr = ProjectManager(conn, tmp_path / "projects")
    proj = proj_mgr.create_project(
        ProjectCreate(
            name="Workflow Test Project",
            chapter_title="Federalism and Centre-State Relations",
            exam_cycle="2026",
            cutoff_date="2026-11-26",
            target_duration_min=5,
            tts_enabled=True,
        )
    )

    runtime = AgentWorkflowRuntime(conn, tmp_path / "projects")

    # 1. Create workflow
    run_id_1 = runtime.create_or_get_workflow(proj.id, target_duration_min=5)
    assert run_id_1.startswith("run_")

    # 2. Idempotency test: repeated create call returns identical run_id
    run_id_2 = runtime.create_or_get_workflow(proj.id, target_duration_min=5)
    assert run_id_1 == run_id_2

    # 3. Check SQLite task records
    tasks = conn.execute("SELECT * FROM workflow_tasks WHERE run_id = ?", (run_id_1,)).fetchall()
    assert len(tasks) == 24
    for t in tasks:
        assert t["status"] == "PENDING"
        assert t["retry_count"] == 0


def test_agent_workflow_dag_topological_sort() -> None:
    sorted_specs = AgentWorkflowRuntime._topological_sort(SPECIALIST_REGISTRY)
    assert len(sorted_specs) == 24

    agent_indices = {spec.agent_id: idx for idx, spec in enumerate(sorted_specs)}
    for spec in sorted_specs:
        for dep in spec.dependencies:
            assert agent_indices[dep] < agent_indices[spec.agent_id], f"Dependency {dep} must execute before {spec.agent_id}."


def test_agent_workflow_recovery_rules_defense(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "test_recovery.db")
    proj_mgr = ProjectManager(conn, tmp_path / "projects")
    proj = proj_mgr.create_project(
        ProjectCreate(
            name="Crash Recovery Project",
            chapter_title="Judicial Review and Basic Structure",
            exam_cycle="2026",
            cutoff_date="2026-11-26",
            target_duration_min=5,
            tts_enabled=True,
        )
    )

    runtime = AgentWorkflowRuntime(conn, tmp_path / "projects")
    run_id = runtime.create_or_get_workflow(proj.id)

    # Simulate an unexpected process exit while two tasks were EXECUTING:
    # 1. AGENT_02 (Topic Researcher: has_side_effects=False, is_retry_safe=True)
    # 2. AGENT_22 (Video Quality Auditor: has_side_effects=True, is_retry_safe=False)
    conn.execute("UPDATE workflow_tasks SET status = 'EXECUTING' WHERE run_id = ? AND agent_id IN ('AGENT_02', 'AGENT_22')", (run_id,))
    conn.commit()

    # Trigger recovery scan
    recovered = runtime.recover_interrupted_workflows()
    assert len(recovered) == 2

    # Verify AGENT_02 was reset to PENDING (safe retry)
    t02 = conn.execute("SELECT status FROM workflow_tasks WHERE run_id = ? AND agent_id = 'AGENT_02'", (run_id,)).fetchone()
    assert t02["status"] == "PENDING"

    # Verify AGENT_22 was flagged as RECOVERY_REVIEW_REQUIRED (no blind replay of side-effecting render!)
    t22 = conn.execute("SELECT status, error_message FROM workflow_tasks WHERE run_id = ? AND agent_id = 'AGENT_22'", (run_id,)).fetchone()
    assert t22["status"] == "RECOVERY_REVIEW_REQUIRED"
    assert "side-effecting task" in t22["error_message"]


def test_agent_workflow_pause_and_status(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "test_pause.db")
    proj_mgr = ProjectManager(conn, tmp_path / "projects")
    proj = proj_mgr.create_project(
        ProjectCreate(
            name="Pause Test Project",
            chapter_title="Separation of Powers",
            exam_cycle="2026",
            cutoff_date="2026-11-26",
            target_duration_min=5,
            tts_enabled=True,
        )
    )

    runtime = AgentWorkflowRuntime(conn, tmp_path / "projects")
    run_id = runtime.create_or_get_workflow(proj.id)

    # Pause workflow
    assert runtime.pause_workflow(run_id) is True

    status_rep = runtime.get_workflow_status(run_id)
    assert status_rep["status"] == "PAUSED"
    assert status_rep["tasks_total"] == 24
    assert status_rep["progress_percentage"] == 0.0

    # Test visual DAG endpoint data
    dag = runtime.get_workflow_dag()
    assert len(dag["nodes"]) == 24
    assert len(dag["edges"]) > 20
