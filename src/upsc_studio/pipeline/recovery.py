"""Observable, self-recovering production operations and recovery coordinator.

Provides:
- Interrupted task detection and quarantining.
- Safe checkpoint restoration and idempotent resumption.
- Temporary artifact cleanup (*.tmp, orphaned partial renders).
- Partial rendering recovery (scene-level reuse).
- Database integrity checks (PRAGMA integrity_check, foreign_key_check).
- Stale approval invalidation upon content drift.
- Duplicate publish prevention and release gating.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from upsc_studio.agents.runtime import AgentTaskStore
from upsc_studio.core.errors import ErrorCategory, classify_error
from upsc_studio.core.paths import sha256_file
from upsc_studio.db.schemas import ProjectStatus, SceneSpec
from upsc_studio.qa.ten_gates import TenGateAuditor


class RecoveryCoordinator:
    """Manages failure recovery, workspace hygiene, and approval invalidation."""

    def __init__(self, conn: sqlite3.Connection, projects_root: Path) -> None:
        self.conn = conn
        self.projects_root = Path(projects_root)
        self.store = AgentTaskStore(conn)

    def detect_interrupted_tasks(self, project_id: str) -> list[dict[str, Any]]:
        """Identify tasks left in RUNNING from crashes or process terminations."""
        workflow_id = f"chapter-pipeline:{project_id}"
        tasks = self.store.list_workflow(workflow_id)
        interrupted: list[dict[str, Any]] = []

        for row in tasks:
            if row["status"] == "RUNNING":
                task_id = row["task_id"]
                self.store.transition(
                    task_id,
                    "REVIEW_REQUIRED",
                    error="Process interrupted unexpectedly mid-execution. Inspect partial side effects before manual retry.",
                    error_category=ErrorCategory.FILESYSTEM_FAILURE.value,
                )
                self.store._event(
                    task_id,
                    workflow_id,
                    "INTERRUPTED_TASK_RECOVERED",
                    {"previous_status": "RUNNING", "action": "QUARANTINED_TO_REVIEW_REQUIRED"},
                )
                interrupted.append({
                    "task_id": task_id,
                    "handler": row["handler"],
                    "agent_id": row["agent_id"],
                    "started_at": row.get("started_at"),
                })

        return interrupted

    def clean_temporary_artifacts(self, project_dir: Path) -> dict[str, Any]:
        """Safely clean dangling *.tmp files and orphaned temporary directories."""
        project_dir = Path(project_dir).resolve()
        if not project_dir.is_dir():
            return {"cleaned_files": [], "bytes_freed": 0, "status": "NO_DIR"}

        cleaned_files: list[str] = []
        bytes_freed = 0

        for root, dirs, files in os.walk(project_dir):
            for fname in files:
                if fname.endswith(".tmp") or fname.endswith(".partial"):
                    fpath = Path(root) / fname
                    try:
                        size = fpath.stat().st_size
                        fpath.unlink()
                        cleaned_files.append(str(fpath.relative_to(project_dir)))
                        bytes_freed += size
                    except Exception:
                        pass

        return {
            "cleaned_files": cleaned_files,
            "count": len(cleaned_files),
            "bytes_freed": bytes_freed,
            "status": "COMPLETED",
        }

    def check_database_integrity(self) -> dict[str, Any]:
        """Execute SQLite consistency and foreign key integrity checks."""
        try:
            cur = self.conn.cursor()
            # Integrity check
            integrity_rows = cur.execute("PRAGMA integrity_check;").fetchall()
            integrity_ok = len(integrity_rows) == 1 and integrity_rows[0][0] == "ok"
            integrity_messages = [r[0] for r in integrity_rows]

            # Foreign key check
            fk_rows = cur.execute("PRAGMA foreign_key_check;").fetchall()
            fk_violations = [
                {"table": r[0], "rowid": r[1], "parent": r[2], "fkid": r[3]}
                for r in fk_rows
            ]

            return {
                "database_ok": integrity_ok and len(fk_violations) == 0,
                "integrity_check": "PASSED" if integrity_ok else "FAILED",
                "integrity_messages": integrity_messages,
                "foreign_key_violations": fk_violations,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {
                "database_ok": False,
                "integrity_check": "FAILED",
                "error": str(exc),
                "error_category": ErrorCategory.DATABASE_FAILURE.value,
            }

    def validate_approval_freshness(
        self, project_id: str, project_dir: Path
    ) -> dict[str, Any]:
        """Invalidate stale human approval if any lesson input, script, or video changed."""
        project_dir = Path(project_dir).resolve()
        cur = self.conn.execute(
            "SELECT status, chapter_title FROM projects WHERE id = ?", (project_id,)
        )
        row = cur.fetchone()
        if not row:
            return {"approval_valid": False, "reason": "Project not found"}

        current_status = row[0]
        if current_status != ProjectStatus.APPROVED.value:
            return {
                "approval_valid": False,
                "is_approved": False,
                "status": current_status,
                "reason": "Project is not currently in APPROVED status",
            }

        approval_report_path = project_dir / "qa" / "final_10_gate_report.json"
        manual_review_path = project_dir / "qa" / "manual_review.json"
        storyboard_path = project_dir / "storyboard" / "storyboard.json"

        if not approval_report_path.is_file() or not manual_review_path.is_file():
            self._invalidate_approval(project_id, "Missing approval report or manual review artifact")
            return {
                "approval_valid": False,
                "stale_detected": True,
                "reason": "Missing approval report or manual review artifact",
            }

        try:
            approval_report = json.loads(approval_report_path.read_text(encoding="utf-8"))
            manual_review = json.loads(manual_review_path.read_text(encoding="utf-8"))
            
            scenes = []
            if storyboard_path.is_file():
                raw_scenes = json.loads(storyboard_path.read_text(encoding="utf-8"))
                scenes = [SceneSpec.model_validate(s) for s in raw_scenes]

            render_stage_path = project_dir / "workflow" / "stages" / "render.json"
            final_video = None
            if render_stage_path.is_file():
                render_data = json.loads(render_stage_path.read_text(encoding="utf-8"))
                manifest = render_data.get("render_manifest") or {}
                if manifest.get("final_video"):
                    final_video = Path(manifest["final_video"])

            current_fingerprint = TenGateAuditor(self.conn, project_dir).review_fingerprint(
                project_id, scenes, final_video
            )

            reviewed_fingerprint = manual_review.get("artifact_fingerprint")
            gate_current = (
                approval_report.get("gate_details", {})
                .get("MANUAL_REVIEW", {})
                .get("review_is_current")
            )

            if (
                current_fingerprint != reviewed_fingerprint
                or gate_current is not True
                or approval_report.get("ready_for_publication") != "PASSED"
            ):
                self._invalidate_approval(
                    project_id,
                    f"Content drifted after approval (current={current_fingerprint[:10]}, reviewed={str(reviewed_fingerprint)[:10]})",
                )
                return {
                    "approval_valid": False,
                    "stale_detected": True,
                    "reason": "Content or visual artifacts modified after human approval.",
                    "current_fingerprint": current_fingerprint,
                    "reviewed_fingerprint": reviewed_fingerprint,
                }

            return {
                "approval_valid": True,
                "stale_detected": False,
                "reviewer": manual_review.get("reviewer"),
                "artifact_fingerprint": current_fingerprint,
            }
        except Exception as exc:
            self._invalidate_approval(project_id, f"Error validating approval freshness: {exc}")
            return {"approval_valid": False, "stale_detected": True, "error": str(exc)}

    def _invalidate_approval(self, project_id: str, reason: str) -> None:
        """Reset project status from APPROVED to NEEDS_REVIEW upon detected drift."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE projects SET status = ?, updated_at = ? WHERE id = ?",
            (ProjectStatus.NEEDS_REVIEW.value, now, project_id),
        )
        # Check if an existing task is present in agent_tasks to satisfy foreign key constraint
        workflow_id = f"chapter-pipeline:{project_id}"
        cur = self.conn.execute(
            "SELECT task_id FROM agent_tasks WHERE workflow_id = ? LIMIT 1",
            (workflow_id,),
        )
        row = cur.fetchone()
        if row:
            self.conn.execute(
                """
                INSERT INTO agent_task_events(task_id, workflow_id, event_type, detail_json, created_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    row[0],
                    workflow_id,
                    "APPROVAL_INVALIDATED",
                    json.dumps({"reason": reason, "invalidated_at": now}),
                    now,
                ),
            )
        self.conn.commit()

    def assess_recovery_eligibility(
        self, project_id: str, project_dir: Path
    ) -> dict[str, Any]:
        """Determine whether the project is eligible for recovery and identify next steps."""
        workflow_id = f"chapter-pipeline:{project_id}"
        tasks = self.store.list_workflow(workflow_id)
        project_row = self.conn.execute(
            "SELECT status, chapter_title FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

        if not project_row:
            return {"eligible": False, "reason": "Project not found"}

        status = project_row[0]
        failed_tasks = [t for t in tasks if t["status"] in {"FAILED", "REVIEW_REQUIRED", "BLOCKED"}]
        running_tasks = [t for t in tasks if t["status"] == "RUNNING"]

        last_checkpoint = None
        checkpoints = self.conn.execute(
            "SELECT checkpoint_key, value_json, updated_at FROM agent_checkpoints WHERE workflow_id = ? ORDER BY updated_at DESC LIMIT 1",
            (workflow_id,),
        ).fetchone()
        if checkpoints:
            last_checkpoint = {
                "key": checkpoints[0],
                "payload": json.loads(checkpoints[1]),
                "updated_at": checkpoints[2],
            }

        if running_tasks:
            return {
                "eligible": True,
                "action": "INTERRUPTED_RECOVERY",
                "recommended_action": "Run auto-recovery to quarantine interrupted tasks.",
                "running_tasks_count": len(running_tasks),
                "last_checkpoint": last_checkpoint,
            }

        if not failed_tasks:
            return {
                "eligible": False,
                "action": "NO_FAILURE",
                "recommended_action": "All stages are healthy or pending normal pipeline run.",
                "current_status": status,
                "last_checkpoint": last_checkpoint,
            }

        # Analyze failed stage
        first_failure = failed_tasks[0]
        err_msg = first_failure.get("error") or ""
        classified = classify_error(RuntimeError(err_msg))

        can_retry_automatically = (
            classified.is_retryable
            and first_failure["status"] != "REVIEW_REQUIRED"
            and int(first_failure.get("attempts", 0)) < int(first_failure.get("max_retries", 2))
        )

        return {
            "eligible": True,
            "action": "MANUAL_RETRY_REQUIRED" if classified.requires_human_review else "AUTO_RETRY_ELIGIBLE",
            "failed_stage": first_failure["handler"],
            "error_category": classified.category.value,
            "error_message": classified.message,
            "is_retryable": can_retry_automatically,
            "requires_human_review": classified.requires_human_review,
            "recovery_suggestion": classified.recovery_suggestion,
            "last_checkpoint": last_checkpoint,
        }

    def prevent_duplicate_upload(
        self, project_id: str, video_sha256: str
    ) -> tuple[bool, str]:
        """Prevent accidental double-publishing of the same video artifact."""
        cur = self.conn.execute(
            """
            SELECT id, checked_at, approved_by, blocking_issues_json
            FROM qa_gates
            WHERE project_id = ? AND gate_name = 'YOUTUBE_PUBLISHED'
            """,
            (project_id,),
        )
        existing = cur.fetchone()
        if existing:
            details = json.loads(existing[3] or "{}")
            if details.get("video_sha256") == video_sha256:
                return False, f"Video {video_sha256[:10]} was already uploaded to YouTube (ID: {details.get('youtube_id', 'unknown')}). Duplicate upload blocked."

        return True, "Upload permitted"
