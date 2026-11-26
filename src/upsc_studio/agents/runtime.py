"""Persistent, dependency-aware task runtime for local-first agent workflows.

The runtime is deliberately framework-light: SQLite is the source of truth, handlers
are explicitly registered by the application, and importing this module never runs work.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping


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
            "RETRY_WAIT": {"RUNNING", "FAILED", "BLOCKED"},
            "RUNNING": {"COMPLETED", "RETRY_WAIT", "FAILED", "REVIEW_REQUIRED"},
            "RETRY_WAIT": {"RUNNING", "FAILED", "BLOCKED", "REVIEW_REQUIRED"},
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
        "independent_agent_count": len(seen) - len(duplicates),
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
        ids = {s.task_id: self.store.enqueue(workflow_id, s, input_fingerprint) for s in items}
        spec_by_id = {s.task_id: s for s in items}
        made_progress = True
        while made_progress:
            made_progress = False
            rows = {s.task_id: self.store.get(ids[s.task_id]) for s in items}
            for spec in items:
                row = rows[spec.task_id]
                if row["status"] in TERMINAL:
                    continue
                dep_rows = [rows[d] for d in spec.depends_on]
                if any(d["status"] in {"FAILED", "BLOCKED"} for d in dep_rows):
                    self.store.transition(ids[spec.task_id], "BLOCKED", error="A dependency did not complete")
                    made_progress = True
                    continue
                if not all(d["status"] == "COMPLETED" for d in dep_rows):
                    continue
                if spec.handler not in self.handlers:
                    self.store.transition(ids[spec.task_id], "FAILED", error=f"No handler registered: {spec.handler}")
                    made_progress = True
                    continue
                self.store.transition(ids[spec.task_id], "RUNNING")
                try:
                    payload = dict(spec.payload)
                    payload["_workflow_id"] = workflow_id
                    payload["_task_id"] = ids[spec.task_id]
                    payload["_dependency_outputs"] = {
                        dep: json.loads(rows[dep]["output_json"] or "{}")
                        for dep in spec.depends_on
                    }
                    output = self.handlers[spec.handler](payload)
                    self.store.transition(ids[spec.task_id], "COMPLETED", output=output)
                except Exception as exc:
                    latest = self.store.get(ids[spec.task_id])
                    if int(latest["attempts"]) <= int(latest["max_retries"]) and isinstance(exc, (TimeoutError, ConnectionError)):
                        self.store.transition(ids[spec.task_id], "RETRY_WAIT", error=f"{type(exc).__name__}: {exc}")
                    else:
                        self.store.transition(ids[spec.task_id], "FAILED", error=f"{type(exc).__name__}: {exc}")
                made_progress = True
        # Retry transient failures in bounded passes, retaining completed task outputs.
        for spec in items:
            task_id = ids[spec.task_id]
            row = self.store.get(task_id)
            while row["status"] == "RETRY_WAIT":
                self.store.transition(task_id, "RUNNING")
                try:
                    payload = dict(spec.payload)
                    payload["_workflow_id"] = workflow_id
                    payload["_task_id"] = task_id
                    payload["_dependency_outputs"] = {
                        dep: json.loads(self.store.get(ids[dep])["output_json"] or "{}")
                        for dep in spec.depends_on
                    }
                    self.store.transition(task_id, "COMPLETED", output=self.handlers[spec.handler](payload))
                except Exception as exc:
                    row = self.store.get(task_id)
                    if int(row["attempts"]) <= int(row["max_retries"]) and isinstance(exc, (TimeoutError, ConnectionError)):
                        self.store.transition(task_id, "RETRY_WAIT", error=f"{type(exc).__name__}: {exc}")
                    else:
                        self.store.transition(task_id, "FAILED", error=f"{type(exc).__name__}: {exc}")
                row = self.store.get(task_id)
        final_rows = [self.store.get(ids[s.task_id]) for s in items]
        statuses = {r["status"] for r in final_rows}
        failed_required = [r["task_id"] for r in final_rows if r["required"] and r["status"] != "COMPLETED"]
        return {
            "workflow_id": workflow_id,
            "status": "COMPLETED" if not failed_required else ("FAILED" if "FAILED" in statuses else "BLOCKED"),
            "task_count": len(items),
            "completed": sum(r["status"] == "COMPLETED" for r in final_rows),
            "failed": sum(r["status"] == "FAILED" for r in final_rows),
            "blocked": sum(r["status"] == "BLOCKED" for r in final_rows),
            "tasks": final_rows,
        }
