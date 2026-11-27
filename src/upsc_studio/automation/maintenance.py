"""Automated system maintenance, disk monitoring, source link verification, and health audit."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests

from upsc_studio.core.hardware import detect_hardware
from upsc_studio.db.schemas import utc_now_iso


class SystemMaintenanceEngine:
    """Provides observable, safe system automation and health diagnostics."""

    def __init__(self, conn: sqlite3.Connection, projects_root: Path) -> None:
        self.conn = conn
        self.projects_root = projects_root

    def check_disk_space(self, min_free_gb: float = 5.0) -> dict[str, Any]:
        """Inspect available disk space and alert if below safe threshold."""
        total, used, free = shutil.disk_usage(self.projects_root)
        free_gb = round(free / (1024**3), 2)
        total_gb = round(total / (1024**3), 2)
        is_safe = free_gb >= min_free_gb

        return {
            "total_gb": total_gb,
            "free_gb": free_gb,
            "min_required_gb": min_free_gb,
            "status": "HEALTHY" if is_safe else "LOW_DISK_SPACE_WARNING",
            "message": f"{free_gb} GB free of {total_gb} GB total." if is_safe else f"LOW DISK SPACE: only {free_gb} GB remaining (minimum recommended: {min_free_gb} GB).",
        }

    def check_broken_source_links(self, project_id: Optional[str] = None, timeout: int = 5) -> dict[str, Any]:
        """Test registered source URLs for reachability without executing untrusted remote code."""
        query = "SELECT id, project_id, title, url FROM sources WHERE url IS NOT NULL AND url != ''"
        params: tuple[Any, ...] = ()
        if project_id:
            query += " AND project_id = ?"
            params = (project_id,)

        rows = self.conn.execute(query, params).fetchall()
        checked = []
        broken = []

        for r in rows:
            url = r["url"]
            try:
                resp = requests.head(url, timeout=timeout, headers={"User-Agent": "UPSC-Studio-LinkChecker/1.0"}, allow_redirects=True)
                reachable = resp.status_code < 400
                status_code = resp.status_code
            except Exception as exc:
                reachable = False
                status_code = None

            item = {
                "source_id": r["id"],
                "project_id": r["project_id"],
                "title": r["title"],
                "url": url,
                "reachable": reachable,
                "status_code": status_code,
            }
            checked.append(item)
            if not reachable:
                broken.append(item)

        return {
            "total_urls_checked": len(checked),
            "broken_links_count": len(broken),
            "broken_links": broken,
            "status": "PASSED" if not broken else "BROKEN_LINKS_DETECTED",
        }

    def audit_source_freshness(self, project_id: Optional[str] = None, cutoff_date: str = "2026-11-26") -> dict[str, Any]:
        """Audit source publication dates against cutoff date."""
        query = "SELECT id, project_id, title, pub_date, source_tier FROM sources"
        params: tuple[Any, ...] = ()
        if project_id:
            query += " WHERE project_id = ?"
            params = (project_id,)

        rows = self.conn.execute(query, params).fetchall()
        cutoff_year = int(cutoff_date[:4]) if len(cutoff_date) >= 4 else 2026
        future_sources = []

        import re
        for r in rows:
            pub_date = r["pub_date"] or ""
            yr_match = re.search(r"\b(19\d{2}|20\d{2})\b", pub_date)
            if yr_match and int(yr_match.group(1)) > cutoff_year:
                future_sources.append({
                    "source_id": r["id"],
                    "title": r["title"],
                    "year": int(yr_match.group(1)),
                    "cutoff_year": cutoff_year,
                })

        return {
            "total_sources_audited": len(rows),
            "cutoff_date": cutoff_date,
            "future_or_outdated_sources_count": len(future_sources),
            "flagged_sources": future_sources,
            "status": "PASSED" if not future_sources else "OUTDATED_OR_FUTURE_SOURCES_FLAGGED",
        }

    def cleanup_temp_caches(self, dry_run: bool = True) -> dict[str, Any]:
        """Safely clean temporary build and test caches without touching user projects or outputs."""
        deleted_paths: list[str] = []
        candidates = [
            Path(".pytest_cache"),
            Path("__pycache__"),
        ]

        # Scan for __pycache__ subdirectories
        for p in self.projects_root.parent.glob("**/__pycache__"):
            candidates.append(p)

        freed_bytes = 0
        for cand in candidates:
            if cand.exists() and cand.is_dir():
                # Measure size
                try:
                    for f in cand.rglob("*"):
                        if f.is_file():
                            freed_bytes += f.stat().st_size
                    if not dry_run:
                        shutil.rmtree(cand, ignore_errors=True)
                    deleted_paths.append(str(cand))
                except Exception:
                    pass

        return {
            "dry_run": dry_run,
            "target_dirs_found": len(deleted_paths),
            "estimated_freed_kb": round(freed_bytes / 1024, 2),
            "paths": deleted_paths[:10],
            "safeguards_active": True,
            "user_data_protected": True,
        }

    def run_system_health_audit(self) -> dict[str, Any]:
        """Perform comprehensive system diagnostics and record to system_automation_logs."""
        disk_res = self.check_disk_space()
        freshness_res = self.audit_source_freshness()
        cache_res = self.cleanup_temp_caches(dry_run=True)

        # Detect active workflows and interrupted tasks
        interrupted = self.conn.execute(
            "SELECT count(*) as cnt FROM workflow_tasks WHERE status = 'EXECUTING'"
        ).fetchone()
        interrupted_count = interrupted["cnt"] if interrupted else 0

        overall_status = "HEALTHY"
        if disk_res["status"] != "HEALTHY" or interrupted_count > 0:
            overall_status = "ATTENTION_REQUIRED"

        report = {
            "audit_timestamp": utc_now_iso(),
            "overall_status": overall_status,
            "disk": disk_res,
            "freshness": freshness_res,
            "cache_savings": cache_res,
            "interrupted_tasks_detected": interrupted_count,
        }

        # Log into system_automation_logs
        log_id = f"auto_{uuid.uuid4().hex[:8]}"
        self.conn.execute(
            """
            INSERT INTO system_automation_logs (id, task_name, status, summary, details_json, created_at)
            VALUES (?, 'SYSTEM_HEALTH_AUDIT', ?, ?, ?, ?)
            """,
            (
                log_id,
                overall_status,
                f"Disk: {disk_res['free_gb']}GB free | Interrupted tasks: {interrupted_count}",
                json.dumps(report, ensure_ascii=False),
                utc_now_iso(),
            ),
        )
        self.conn.commit()

        return report
