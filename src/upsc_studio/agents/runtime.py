"""SQLite-backed persistent workflow engine and runtime for autonomous specialist agents."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from upsc_studio.agents.contracts import (
    AgentExecutionContext,
    AgentExecutionResult,
    AgentRole,
    AgentStatus,
    AgentTaskSpec,
    QualityCheckStatus,
    SPECIALIST_REGISTRY,
)
from upsc_studio.agents.specialists.factory import get_specialist_agent
from upsc_studio.db.schemas import utc_now_iso


class AgentWorkflowRuntime:
    """Manages persistent DAG workflow runs, task checkpoints, crash recovery, and idempotency."""

    def __init__(self, conn: sqlite3.Connection, projects_root: Path) -> None:
        self.conn = conn
        self.projects_root = projects_root

    def create_or_get_workflow(
        self,
        project_id: str,
        content_pillar: str = "UPSC_CIVIL_SERVICES",
        target_duration_min: int = 15,
    ) -> str:
        """Create a new workflow run or return existing active run to avoid duplicate records."""
        # Check for existing active or paused workflow
        existing = self.conn.execute(
            """
            SELECT id FROM workflow_runs
            WHERE project_id = ? AND status IN ('REGISTERED', 'EXECUTING', 'PAUSED')
            ORDER BY started_at DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()

        if existing:
            return existing["id"]

        run_id = f"run_{uuid.uuid4().hex[:10]}"
        now = utc_now_iso()

        self.conn.execute(
            """
            INSERT INTO workflow_runs (
                id, project_id, status, content_pillar, target_duration_min,
                started_at, metadata_json
            ) VALUES (?, ?, 'REGISTERED', ?, ?, ?, '{}')
            """,
            (run_id, project_id, content_pillar, target_duration_min, now),
        )

        # Seed initial tasks from SPECIALIST_REGISTRY
        for spec in SPECIALIST_REGISTRY:
            task_id = f"task_{run_id}_{spec.agent_id}"
            self.conn.execute(
                """
                INSERT INTO workflow_tasks (
                    id, run_id, agent_id, agent_role, status,
                    is_retry_safe, has_side_effects, retry_count, max_retries,
                    input_json, output_json, error_message
                ) VALUES (?, ?, ?, ?, 'PENDING', ?, ?, 0, ?, '{}', '{}', '')
                """,
                (
                    task_id,
                    run_id,
                    spec.agent_id,
                    spec.role.value,
                    1 if spec.is_retry_safe else 0,
                    1 if spec.has_side_effects else 0,
                    spec.max_retries,
                ),
            )
        self.conn.commit()
        return run_id

    def execute_workflow(self, run_id: str, resume: bool = False) -> dict[str, Any]:
        """Execute the DAG workflow honoring task dependencies, retries, idempotency, and pause signals."""
        run_row = self.conn.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
        if not run_row:
            raise ValueError(f"Workflow run '{run_id}' not found.")

        project_id = run_row["project_id"]
        proj_row = self.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not proj_row:
            raise ValueError(f"Project '{project_id}' not found.")

        project_dir = Path(proj_row["root_dir"])
        content_pillar = run_row["content_pillar"]
        target_duration_min = run_row["target_duration_min"]
        cutoff_date = proj_row["cutoff_date"]

        # Mark workflow as EXECUTING
        self.conn.execute("UPDATE workflow_runs SET status = 'EXECUTING' WHERE id = ?", (run_id,))
        self.conn.commit()

        # Build task execution graph in topological dependency order
        ordered_specs = self._topological_sort(SPECIALIST_REGISTRY)

        # In-memory accumulator of upstream outputs
        accumulated_outputs: dict[str, Any] = {}

        # Preload any previously completed tasks (idempotency support)
        task_rows = self.conn.execute("SELECT * FROM workflow_tasks WHERE run_id = ?", (run_id,)).fetchall()
        task_map = {r["agent_id"]: dict(r) for r in task_rows}

        for r in task_rows:
            if r["status"] == "COMPLETED" and r["output_json"]:
                try:
                    accumulated_outputs[r["agent_id"]] = json.loads(r["output_json"])
                except Exception:
                    pass

        has_failure = False

        for spec in ordered_specs:
            agent_id = spec.agent_id
            task_info = task_map.get(agent_id, {})
            task_db_id = task_info.get("id", f"task_{run_id}_{agent_id}")

            # 1. Check for manual PAUSE request
            current_run = self.conn.execute("SELECT status FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
            if current_run and current_run["status"] == "PAUSED":
                return self.get_workflow_status(run_id)

            # 2. Check for RECOVERY_REVIEW_REQUIRED
            if task_info.get("status") == "RECOVERY_REVIEW_REQUIRED":
                self.conn.execute("UPDATE workflow_runs SET status = 'RECOVERY_REVIEW_REQUIRED' WHERE id = ?", (run_id,))
                self.conn.commit()
                return self.get_workflow_status(run_id)

            # 3. Idempotency Check: Skip already completed tasks
            if resume and task_info.get("status") == "COMPLETED":
                continue

            # 4. Dependency failure propagation
            blocked_reasons: list[str] = []
            for dep_id in spec.dependencies:
                dep_status = task_map.get(dep_id, {}).get("status")
                if dep_status != "COMPLETED":
                    blocked_reasons.append(f"Upstream agent '{dep_id}' status is '{dep_status}'.")

            if blocked_reasons:
                self.conn.execute(
                    """
                    UPDATE workflow_tasks
                    SET status = 'BLOCKED', error_message = ?
                    WHERE id = ?
                    """,
                    ("; ".join(blocked_reasons), task_db_id),
                )
                self.conn.commit()
                task_map[agent_id]["status"] = "BLOCKED"
                has_failure = True
                continue

            # 5. Execute task with bounded retries
            agent = get_specialist_agent(agent_id)
            if not agent:
                self.conn.execute(
                    "UPDATE workflow_tasks SET status = 'FAILED', error_message = ? WHERE id = ?",
                    (f"No specialist agent registered for {agent_id}", task_db_id),
                )
                self.conn.commit()
                task_map[agent_id]["status"] = "FAILED"
                has_failure = True
                continue

            # Mark task EXECUTING
            now_iso = utc_now_iso()
            self.conn.execute(
                "UPDATE workflow_tasks SET status = 'EXECUTING', started_at = ? WHERE id = ?",
                (now_iso, task_db_id),
            )
            self.conn.execute("UPDATE workflow_runs SET current_task_id = ? WHERE id = ?", (task_db_id, run_id))
            self.conn.commit()

            context = AgentExecutionContext(
                project_id=project_id,
                project_dir=project_dir,
                run_id=run_id,
                topic_title=proj_row["chapter_title"],
                content_pillar=content_pillar,
                cutoff_date=cutoff_date,
                target_duration_min=target_duration_min,
                tts_enabled=bool(proj_row["tts_enabled"]),
                upstream_outputs=accumulated_outputs,
                metadata={"conn": self.conn},
            )

            success = False
            max_retries = spec.max_retries if spec.is_retry_safe else 0
            retries_attempted = 0
            last_result: Optional[AgentExecutionResult] = None

            for attempt in range(max_retries + 1):
                res = agent.run(context)
                last_result = res
                if res.status == AgentStatus.COMPLETED:
                    success = True
                    break
                else:
                    retries_attempted = attempt
                    if attempt < max_retries:
                        time.sleep(0.1 * (2**attempt))

            completed_at = utc_now_iso()
            if success and last_result:
                output_json = json.dumps(last_result.outputs, ensure_ascii=False)
                accumulated_outputs[agent_id] = last_result.outputs
                self.conn.execute(
                    """
                    UPDATE workflow_tasks
                    SET status = 'COMPLETED', output_json = ?, retry_count = ?, completed_at = ?
                    WHERE id = ?
                    """,
                    (output_json, retries_attempted, completed_at, task_db_id),
                )
                task_map[agent_id]["status"] = "COMPLETED"

                # Save checkpoint in SQLite
                chk_id = f"chk_{uuid.uuid4().hex[:8]}"
                self.conn.execute(
                    """
                    INSERT INTO workflow_checkpoints (id, run_id, task_id, checkpoint_name, state_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (chk_id, run_id, task_db_id, f"AFTER_{agent_id}", output_json, completed_at),
                )
            else:
                err_msg = "; ".join(last_result.errors) if last_result else "Execution failed."
                self.conn.execute(
                    """
                    UPDATE workflow_tasks
                    SET status = 'FAILED', error_message = ?, retry_count = ?, completed_at = ?
                    WHERE id = ?
                    """,
                    (err_msg, retries_attempted, completed_at, task_db_id),
                )
                task_map[agent_id]["status"] = "FAILED"
                has_failure = True

            self.conn.commit()

        final_status = "COMPLETED" if not has_failure else "FAILED"
        self.conn.execute(
            """
            UPDATE workflow_runs
            SET status = ?, completed_at = ?, current_task_id = NULL
            WHERE id = ?
            """,
            (final_status, utc_now_iso(), run_id),
        )
        self.conn.commit()

        return self.get_workflow_status(run_id)

    def pause_workflow(self, run_id: str) -> bool:
        """Mark workflow as PAUSED. Ongoing task completes and subsequent tasks halt."""
        self.conn.execute("UPDATE workflow_runs SET status = 'PAUSED' WHERE id = ?", (run_id,))
        self.conn.commit()
        return True

    def resume_workflow(self, run_id: str) -> dict[str, Any]:
        """Resume a paused or interrupted workflow."""
        return self.execute_workflow(run_id, resume=True)

    def recover_interrupted_workflows(self) -> list[dict[str, Any]]:
        """Identify tasks interrupted during an unexpected shutdown.
        
        Strict Recovery Rules:
        - NEVER blindly replay an interrupted side-effecting task.
        - If task.has_side_effects == 1: mark as RECOVERY_REVIEW_REQUIRED.
        - If task.is_retry_safe == 1 and not has_side_effects: reset to PENDING.
        """
        interrupted_tasks = self.conn.execute(
            """
            SELECT t.*, r.project_id
            FROM workflow_tasks t
            JOIN workflow_runs r ON t.run_id = r.id
            WHERE t.status = 'EXECUTING'
            """
        ).fetchall()

        recovered_items = []
        for t in interrupted_tasks:
            t_id = t["id"]
            run_id = t["run_id"]
            has_side_effects = bool(t["has_side_effects"])

            if has_side_effects:
                self.conn.execute(
                    """
                    UPDATE workflow_tasks
                    SET status = 'RECOVERY_REVIEW_REQUIRED',
                        error_message = 'Process terminated mid-execution on a side-effecting task. Manual inspection required before rerun.'
                    WHERE id = ?
                    """,
                    (t_id,),
                )
                self.conn.execute(
                    "UPDATE workflow_runs SET status = 'RECOVERY_REVIEW_REQUIRED' WHERE id = ?", (run_id,)
                )
                recovered_items.append({"task_id": t_id, "action": "FLAGGED_FOR_MANUAL_REVIEW"})
            else:
                self.conn.execute(
                    "UPDATE workflow_tasks SET status = 'PENDING', error_message = 'Reset to PENDING after safe restart.' WHERE id = ?",
                    (t_id,),
                )
                recovered_items.append({"task_id": t_id, "action": "RESET_TO_PENDING"})

        self.conn.commit()
        return recovered_items

    def get_workflow_status(self, run_id: str) -> dict[str, Any]:
        """Return comprehensive status, task progression, and checkpoints for a workflow run."""
        run = self.conn.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
        if not run:
            return {"error": f"Workflow run {run_id} not found."}

        tasks = self.conn.execute(
            "SELECT * FROM workflow_tasks WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()

        checkpoints = self.conn.execute(
            "SELECT * FROM workflow_checkpoints WHERE run_id = ? ORDER BY created_at", (run_id,)
        ).fetchall()

        total = len(tasks)
        completed = sum(1 for t in tasks if t["status"] == "COMPLETED")
        pct = round((completed / total * 100.0), 1) if total > 0 else 0.0

        return {
            "run_id": run["id"],
            "project_id": run["project_id"],
            "status": run["status"],
            "content_pillar": run["content_pillar"],
            "target_duration_min": run["target_duration_min"],
            "current_task_id": run["current_task_id"],
            "progress_percentage": pct,
            "tasks_completed": completed,
            "tasks_total": total,
            "started_at": run["started_at"],
            "completed_at": run["completed_at"],
            "tasks": [dict(t) for t in tasks],
            "checkpoints": [dict(c) for c in checkpoints],
        }

    @staticmethod
    def get_workflow_dag() -> dict[str, Any]:
        """Return visual DAG node and edge data for frontend diagram rendering."""
        nodes = []
        edges = []
        for spec in SPECIALIST_REGISTRY:
            nodes.append({
                "id": spec.agent_id,
                "label": spec.name,
                "role": spec.role.value,
                "is_retry_safe": spec.is_retry_safe,
                "has_side_effects": spec.has_side_effects,
                "description": spec.description,
            })
            for dep in spec.dependencies:
                edges.append({"from": dep, "to": spec.agent_id})

        return {"nodes": nodes, "edges": edges}

    @staticmethod
    def _topological_sort(specs: list[AgentTaskSpec]) -> list[AgentTaskSpec]:
        """Perform deterministic topological sort of DAG task specifications."""
        spec_map = {s.agent_id: s for s in specs}
        in_degree = {s.agent_id: len(s.dependencies) for s in specs}
        dep_graph: dict[str, list[str]] = {s.agent_id: [] for s in specs}

        for s in specs:
            for dep in s.dependencies:
                if dep in dep_graph:
                    dep_graph[dep].append(s.agent_id)

        queue = [s.agent_id for s in specs if in_degree[s.agent_id] == 0]
        sorted_ids = []

        while queue:
            curr = queue.pop(0)
            sorted_ids.append(curr)
            for child in dep_graph.get(curr, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        return [spec_map[aid] for aid in sorted_ids if aid in spec_map]
