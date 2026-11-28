"""Runtime monitoring, live stage progress and system resource tracking."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import psutil

from upsc_studio.agents.runtime import AgentTaskStore
from upsc_studio.core.hardware import detect_hardware
from upsc_studio.pipeline.recovery import RecoveryCoordinator


class RuntimeMonitor:
    """Collects live pipeline state, task execution metrics and system health."""

    def __init__(self, conn: sqlite3.Connection, projects_root: Path) -> None:
        self.conn = conn
        self.projects_root = Path(projects_root)
        self.store = AgentTaskStore(conn)
        self.recovery = RecoveryCoordinator(conn, projects_root)

    def sample_system_resources(self) -> dict[str, Any]:
        """Sample current CPU, RAM, and Disk metrics without blocking."""
        try:
            mem = psutil.virtual_memory()
            disk = shutil.disk_usage(str(self.projects_root))
            process = psutil.Process()
            proc_mem = process.memory_info()

            return {
                "system_cpu_percent": psutil.cpu_percent(interval=None),
                "process_cpu_percent": process.cpu_percent(interval=None),
                "process_memory_rss_mb": round(proc_mem.rss / (1024 * 1024), 2),
                "system_memory_used_percent": mem.percent,
                "system_memory_available_gb": round(mem.available / (1024**3), 2),
                "free_disk_gb": round(disk.free / (1024**3), 2),
                "sampled_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {
                "error": str(exc),
                "sampled_at": datetime.now(timezone.utc).isoformat(),
            }

    def get_live_project_status(self, project_id: str) -> dict[str, Any]:
        """Aggregate end-to-end operational observability for a project."""
        project_row = self.conn.execute(
            """
            SELECT id, name, slug, chapter_title, content_category,
                   exam_cycle, cutoff_date, target_duration_min,
                   tts_enabled, root_dir, status, created_at, updated_at
            FROM projects WHERE id = ?
            """,
            (project_id,),
        ).fetchone()

        if not project_row:
            return {"error": "Project not found", "project_id": project_id}

        project_dir = Path(project_row[9]).resolve()
        workflow_id = f"chapter-pipeline:{project_id}"
        tasks = self.store.list_workflow(workflow_id)

        # 1. Pipeline stage progress (7 core stages)
        stage_names = [
            ("ingestion", "pipeline_ingestion"),
            ("academic", "pipeline_academic"),
            ("teaching", "pipeline_teaching"),
            ("visuals", "pipeline_visuals"),
            ("voice", "pipeline_voice"),
            ("render", "pipeline_render"),
            ("qa", "pipeline_qa"),
        ]
        
        task_by_handler = {t["handler"]: t for t in tasks}
        stage_progress = []
        for stage_code, handler in stage_names:
            t = task_by_handler.get(handler)
            if t:
                duration = t.get("duration_sec")
                if duration is None and t.get("started_at") and t.get("finished_at"):
                    try:
                        s = datetime.fromisoformat(t["started_at"])
                        f = datetime.fromisoformat(t["finished_at"])
                        duration = round((f - s).total_seconds(), 2)
                    except Exception:
                        pass

                stage_progress.append({
                    "stage": stage_code,
                    "handler": handler,
                    "task_id": t["task_id"],
                    "status": t["status"],
                    "attempts": t["attempts"],
                    "max_retries": t["max_retries"],
                    "started_at": t.get("started_at"),
                    "finished_at": t.get("finished_at"),
                    "duration_sec": duration,
                    "error": t.get("error"),
                    "error_category": t.get("error_category"),
                })
            else:
                stage_progress.append({
                    "stage": stage_code,
                    "handler": handler,
                    "task_id": None,
                    "status": "NOT_STARTED",
                    "attempts": 0,
                    "max_retries": 2,
                    "started_at": None,
                    "finished_at": None,
                    "duration_sec": None,
                    "error": None,
                    "error_category": None,
                })

        # 2. Output artifact references
        stages_dir = project_dir / "workflow" / "stages"
        artifacts: dict[str, Any] = {}
        if stages_dir.is_dir():
            for f in stages_dir.glob("*.json"):
                artifacts[f.stem] = str(f.relative_to(project_dir))

        # Check for media outputs
        render_stage_file = stages_dir / "render.json"
        video_output = None
        if render_stage_file.is_file():
            try:
                rdata = json.loads(render_stage_file.read_text(encoding="utf-8"))
                manifest = rdata.get("render_manifest") or {}
                video_output = manifest.get("final_video")
            except Exception:
                pass

        # 3. Last successful checkpoint
        checkpoint_row = self.conn.execute(
            """
            SELECT checkpoint_key, value_json, updated_at
            FROM agent_checkpoints
            WHERE workflow_id = ?
            ORDER BY updated_at DESC LIMIT 1
            """,
            (workflow_id,),
        ).fetchone()
        last_checkpoint = None
        if checkpoint_row:
            last_checkpoint = {
                "key": checkpoint_row[0],
                "payload": json.loads(checkpoint_row[1]),
                "updated_at": checkpoint_row[2],
            }

        # 4. Recovery eligibility
        recovery_info = self.recovery.assess_recovery_eligibility(project_id, project_dir)

        # 5. QA and Research summaries
        verified_claims = self.conn.execute(
            "SELECT count(*) FROM claims WHERE project_id = ? AND status = 'VERIFIED'",
            (project_id,),
        ).fetchone()[0]
        total_claims = self.conn.execute(
            "SELECT count(*) FROM claims WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        sources_count = self.conn.execute(
            "SELECT count(*) FROM sources WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]

        # 6. Database and resource metrics
        db_integrity = self.recovery.check_database_integrity()
        resources = self.sample_system_resources()

        completed_count = sum(1 for s in stage_progress if s["status"] == "COMPLETED")
        overall_progress_pct = round((completed_count / len(stage_names)) * 100, 1)

        return {
            "project_id": project_id,
            "project_name": project_row[1],
            "chapter_title": project_row[3],
            "content_category": project_row[4],
            "overall_status": project_row[10],
            "overall_progress_pct": overall_progress_pct,
            "stages": stage_progress,
            "artifacts": artifacts,
            "final_video": video_output,
            "research_summary": {
                "sources_count": sources_count,
                "verified_claims": verified_claims,
                "total_claims": total_claims,
            },
            "last_checkpoint": last_checkpoint,
            "recovery_eligibility": recovery_info,
            "database_integrity": db_integrity,
            "system_resources": resources,
            "reported_at": datetime.now(timezone.utc).isoformat(),
        }
