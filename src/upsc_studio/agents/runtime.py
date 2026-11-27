"""SQLite-backed persistent workflow engine and runtime for autonomous specialist agents."""

from __future__ import annotations

import hashlib
import importlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional

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


TERMINAL = {"COMPLETED", "FAILED", "BLOCKED", "SKIPPED", "REVIEW_REQUIRED"}
ACTIVE = {"PENDING", "RUNNING", "RETRY_WAIT"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _row_dict(cursor: sqlite3.Cursor, row: tuple | None) -> dict | None:
    if row is None:
        return None
    return dict(zip((c[0] for c in cursor.description), row))


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    agent_id: str
    handler: str
    depends_on: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)
    required: bool = True
    max_retries: int = 2
    retry_safe: bool = False

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.agent_id.strip() or not self.handler.strip():
            raise ValueError("task_id, agent_id and handler are required")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")


class AgentTaskStore:
    """SQLite-backed queue with idempotency, checkpoints and append-only events."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS agent_tasks (
            task_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            handler TEXT NOT NULL,
            depends_on_json TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            required INTEGER NOT NULL DEFAULT 1,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 2,
            output_json TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_agent_tasks_workflow_status
            ON agent_tasks(workflow_id, status);
        CREATE TABLE IF NOT EXISTS agent_checkpoints (
            workflow_id TEXT NOT NULL,
            checkpoint_key TEXT NOT NULL,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(workflow_id, checkpoint_key)
        );
        CREATE TABLE IF NOT EXISTS agent_task_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            workflow_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            detail_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(task_id) REFERENCES agent_tasks(task_id)
        );
        """)
        self.conn.commit()

    def _event(self, task_id: str, workflow_id: str, event: str, detail: Any = None) -> None:
        self.conn.execute(
            "INSERT INTO agent_task_events(task_id, workflow_id, event_type, detail_json, created_at) VALUES(?,?,?,?,?)",
            (task_id, workflow_id, event, _json(detail or {}), _now()),
        )

    def enqueue(self, workflow_id: str, spec: TaskSpec, input_fingerprint: str = "") -> str:
        if not workflow_id.strip():
            raise ValueError("workflow_id is required")
        key_material = _json({"workflow_id": workflow_id, "task_id": spec.task_id, "agent_id": spec.agent_id, "handler": spec.handler, "input_fingerprint": input_fingerprint, "payload": dict(spec.payload), "depends_on": list(spec.depends_on), "required": spec.required, "max_retries": spec.max_retries, "retry_safe": spec.retry_safe})
        idem = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
        existing = self.conn.execute(
            "SELECT task_id FROM agent_tasks WHERE idempotency_key=?", (idem,)
        ).fetchone()
        if existing:
            return str(existing[0])
        now = _now()
        task_id = f"task_{uuid.uuid4().hex}"
        self.conn.execute(
            """INSERT INTO agent_tasks
            (task_id,workflow_id,agent_id,handler,depends_on_json,payload_json,idempotency_key,
             status,required,attempts,max_retries,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (task_id, workflow_id, spec.agent_id, spec.handler, _json(list(spec.depends_on)),
             _json(dict(spec.payload)), idem, "PENDING", int(spec.required), 0,
             spec.max_retries, now, now),
        )
        self._event(task_id, workflow_id, "ENQUEUED", {"agent_id": spec.agent_id})
        self.conn.commit()
        return task_id

    def get(self, task_id: str) -> dict | None:
        cur = self.conn.execute("SELECT * FROM agent_tasks WHERE task_id=?", (task_id,))
        return _row_dict(cur, cur.fetchone())

    def list_workflow(self, workflow_id: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM agent_tasks WHERE workflow_id=? ORDER BY created_at, task_id", (workflow_id,)
        )
        return [_row_dict(cur, row) for row in cur.fetchall()]  # type: ignore[misc]

    def transition(self, task_id: str, status: str, *, output: Any = None, error: str | None = None) -> None:
        allowed = {
            "PENDING": {"RUNNING", "BLOCKED", "SKIPPED"},
            "RETRY_WAIT": {"RUNNING", "FAILED", "BLOCKED", "REVIEW_REQUIRED"},
            "RUNNING": {"COMPLETED", "RETRY_WAIT", "FAILED", "REVIEW_REQUIRED"},
        }
        row = self.get(task_id)
        if row is None:
            raise KeyError(task_id)
        old = row["status"]
        if status not in allowed.get(old, set()):
            raise ValueError(f"invalid task transition: {old} -> {status}")
        now = _now()
        started = now if status == "RUNNING" and not row["started_at"] else row["started_at"]
        finished = now if status in TERMINAL else None
        attempts = int(row["attempts"]) + (1 if status == "RUNNING" else 0)
        self.conn.execute(
            """UPDATE agent_tasks SET status=?, output_json=?, error=?, attempts=?,
            updated_at=?, started_at=?, finished_at=? WHERE task_id=?""",
            (status, _json(output) if output is not None else row["output_json"], error,
             attempts, now, started, finished, task_id),
        )
        self._event(task_id, row["workflow_id"], status, {"error": error} if error else output)
        self.conn.commit()

    def quarantine_interrupted(self, workflow_id: str) -> list[str]:
        """Move crash-interrupted handlers to review; never replay unknown side effects."""
        quarantined = []
        for row in self.list_workflow(workflow_id):
            if row["status"] == "RUNNING":
                self.transition(row["task_id"], "REVIEW_REQUIRED",
                                error="Handler was interrupted; inspect side effects before manual recovery.")
                quarantined.append(row["task_id"])
        return quarantined

    def checkpoint(self, workflow_id: str, key: str, value: Any) -> None:
        self.conn.execute(
            """INSERT INTO agent_checkpoints(workflow_id,checkpoint_key,value_json,updated_at)
            VALUES(?,?,?,?) ON CONFLICT(workflow_id,checkpoint_key) DO UPDATE SET
            value_json=excluded.value_json, updated_at=excluded.updated_at""",
            (workflow_id, key, _json(value), _now()),
        )
        self.conn.commit()

    def read_checkpoint(self, workflow_id: str, key: str) -> Any:
        row = self.conn.execute(
            "SELECT value_json FROM agent_checkpoints WHERE workflow_id=? AND checkpoint_key=?",
            (workflow_id, key),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def events(self, workflow_id: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM agent_task_events WHERE workflow_id=? ORDER BY event_id", (workflow_id,)
        )
        return [_row_dict(cur, row) for row in cur.fetchall()]  # type: ignore[misc]


def inspect_agent_registry(registry: Iterable[Mapping[str, Any]]) -> dict:
    """Import-check registry targets and report duplicate targets without overstating agents."""
    seen: dict[str, list[str]] = {}
    results = []
    for item in registry:
        agent_id = str(item.get("id", ""))
        target = str(item.get("module", ""))
        seen.setdefault(target, []).append(agent_id)
        try:
            module_name, attr = target.rsplit(".", 1)
            module = importlib.import_module(module_name)
            getattr(module, attr)
            results.append({"id": agent_id, "target": target, "importable": True, "error": None})
        except Exception as exc:  # registry diagnostics must report, not crash the app
            results.append({"id": agent_id, "target": target, "importable": False,
                            "error": f"{type(exc).__name__}: {exc}"})
    duplicates = {target: ids for target, ids in seen.items() if target and len(ids) > 1}
    return {
        "registered_entries": len(results),
        "importable_entries": sum(bool(r["importable"]) for r in results),
        "failed_entries": [r for r in results if not r["importable"]],
        "duplicate_implementation_targets": duplicates,
        "entries": results,
        "unique_implementation_target_count": len([target for target in seen if target]),
        "duplicate_registry_entry_count": sum(len(ids) - 1 for ids in duplicates.values()),
    }


class DependencyScheduler:
    """Deterministic sequential DAG runner; safe default for CPU-limited local machines."""

    def __init__(self, store: AgentTaskStore, handlers: Mapping[str, Callable[[dict], Any]]) -> None:
        self.store = store
        self.handlers = dict(handlers)

    @staticmethod
    def validate(specs: Iterable[TaskSpec]) -> list[TaskSpec]:
        items = list(specs)
        by_id = {s.task_id: s for s in items}
        if len(by_id) != len(items):
            raise ValueError("duplicate task_id in workflow")
        for spec in items:
            missing = set(spec.depends_on) - set(by_id)
            if missing:
                raise ValueError(f"{spec.task_id} has unknown dependencies: {sorted(missing)}")
            if spec.task_id in spec.depends_on:
                raise ValueError(f"{spec.task_id} cannot depend on itself")
        visiting: set[str] = set()
        visited: set[str] = set()
        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise ValueError("dependency cycle detected")
            if task_id in visited:
                return
            visiting.add(task_id)
            for dep in by_id[task_id].depends_on:
                visit(dep)
            visiting.remove(task_id)
            visited.add(task_id)
        for task_id in by_id:
            visit(task_id)
        return items

    def run(self, workflow_id: str, specs: Iterable[TaskSpec], *, input_fingerprint: str = "") -> dict:
        items = self.validate(specs)
        if not workflow_id.strip():
            raise ValueError("workflow_id is required")
        ids = {s.task_id: self.store.enqueue(workflow_id, s, input_fingerprint) for s in items}
        self.store.quarantine_interrupted(workflow_id)
        if not items:
            return {"workflow_id": workflow_id, "status": "COMPLETED", "task_count": 0, "completed": 0, "failed": 0, "blocked": 0, "review_required": 0, "tasks": []}
        progress = True
        while progress:
            progress = False
            rows = {s.task_id: self.store.get(ids[s.task_id]) for s in items}
            for spec in items:
                task_id = ids[spec.task_id]
                row = rows[spec.task_id]
                if row["status"] in TERMINAL or row["status"] == "RUNNING":
                    continue
                deps = [rows[d] for d in spec.depends_on]
                if any(d["status"] in {"FAILED", "BLOCKED", "SKIPPED", "REVIEW_REQUIRED"} for d in deps):
                    self.store.transition(task_id, "BLOCKED", error="A dependency did not complete successfully")
                    progress = True
                    continue
                if not all(d["status"] == "COMPLETED" for d in deps):
                    continue
                if spec.handler not in self.handlers:
                    self.store.transition(task_id, "FAILED", error=f"No handler registered: {spec.handler}")
                    progress = True
                    continue
                if row["status"] == "RETRY_WAIT" and not spec.retry_safe:
                    self.store.transition(task_id, "REVIEW_REQUIRED", error="Retry pending after restart; handler is not declared retry-safe.")
                    progress = True
                    continue
                while True:
                    self.store.transition(task_id, "RUNNING")
                    try:
                        payload = dict(spec.payload)
                        payload["_workflow_id"] = workflow_id
                        payload["_task_id"] = task_id
                        payload["_dependency_outputs"] = {dep: json.loads(self.store.get(ids[dep])["output_json"] or "{}") for dep in spec.depends_on}
                        output = self.handlers[spec.handler](payload)
                        business_status = output.get("status") if isinstance(output, Mapping) else None
                        task_status = business_status if business_status in {"FAILED", "BLOCKED", "REVIEW_REQUIRED", "SKIPPED"} else "COMPLETED"
                        task_error = output.get("error") if task_status != "COMPLETED" and isinstance(output, Mapping) else None
                        self.store.transition(task_id, task_status, output=output, error=task_error)
                        progress = True
                        break
                    except Exception as exc:
                        latest = self.store.get(task_id)
                        transient = isinstance(exc, (TimeoutError, ConnectionError))
                        retry = transient and spec.retry_safe and int(latest["attempts"]) <= int(latest["max_retries"])
                        if retry:
                            self.store.transition(task_id, "RETRY_WAIT", error=f"{type(exc).__name__}: {exc}")
                            continue
                        self.store.transition(task_id, "FAILED" if not transient else "REVIEW_REQUIRED", error=f"{type(exc).__name__}: {exc}")
                        progress = True
                        break
        final_rows = [self.store.get(ids[s.task_id]) for s in items]
        failed_required = [r for r in final_rows if r["required"] and r["status"] != "COMPLETED"]
        review_count = sum(r["status"] == "REVIEW_REQUIRED" for r in final_rows)
        statuses = {r["status"] for r in final_rows}
        overall = "COMPLETED" if not failed_required else ("REVIEW_REQUIRED" if review_count else ("FAILED" if "FAILED" in statuses else "BLOCKED"))
        return {"workflow_id": workflow_id, "status": overall, "task_count": len(items),
                "completed": sum(r["status"] == "COMPLETED" for r in final_rows),
                "failed": sum(r["status"] == "FAILED" for r in final_rows),
                "blocked": sum(r["status"] == "BLOCKED" for r in final_rows),
                "review_required": review_count, "tasks": final_rows}


def create_default_scheduler(conn: sqlite3.Connection) -> DependencyScheduler:
    """Create the SQLite-backed scheduler with the built-in deterministic audit workers."""
    from upsc_studio.agents.workers import default_worker_handlers

    return DependencyScheduler(AgentTaskStore(conn), default_worker_handlers())
