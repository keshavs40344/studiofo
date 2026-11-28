"""Multi-chapter batch production orchestrator with CPU/RAM load throttling.

Executes a queue of chapter projects sequentially or with bounded concurrency
while enforcing disk space, memory, and CPU safety thresholds on Windows laptops.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import psutil

from upsc_studio.core.errors import ErrorCategory, classify_error
from upsc_studio.core.hardware import check_disk_space_ok, detect_hardware
from upsc_studio.db.schemas import ProjectStatus
from upsc_studio.pipeline.staged import StagedChapterPipeline
from upsc_studio.projects.manager import ProjectManager


@dataclass
class BatchJobItem:
    """Single chapter job inside a batch queue."""
    project_id: str
    notes_files: list[Path] = field(default_factory=list)
    typed_notes: str = ""
    voice_path: Optional[Path] = None
    ai_narration: bool = False


class BatchProductionOrchestrator:
    """CPU-safe, resumable batch runner for multi-chapter documentary production."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        projects_root: Path,
        max_ram_percent: float = 88.0,
        min_free_disk_gb: float = 1.5,
    ) -> None:
        self.conn = conn
        self.projects_root = Path(projects_root).resolve()
        self.max_ram_percent = max_ram_percent
        self.min_free_disk_gb = min_free_disk_gb
        self.project_mgr = ProjectManager(conn, self.projects_root)
        self.pipeline = StagedChapterPipeline(conn, self.projects_root)

    def check_resource_guard(self) -> tuple[bool, dict[str, Any]]:
        """Verify CPU, memory, and disk headroom before starting the next chapter."""
        mem = psutil.virtual_memory()
        ok_disk, free_gb = check_disk_space_ok(self.projects_root, min_free_gb=self.min_free_disk_gb)
        hw = detect_hardware(self.projects_root)

        metrics = {
            "ram_used_percent": mem.percent,
            "max_ram_percent": self.max_ram_percent,
            "free_disk_gb": free_gb,
            "min_free_disk_gb": self.min_free_disk_gb,
            "max_concurrent_jobs": min(1, hw.max_concurrent_jobs),  # Strict sequential default on i5
        }

        if not ok_disk:
            return False, {**metrics, "reason": f"Insufficient disk space ({free_gb} GB < {self.min_free_disk_gb} GB)."}
        if mem.percent >= self.max_ram_percent:
            return False, {**metrics, "reason": f"Memory pressure too high ({mem.percent}% >= {self.max_ram_percent}%)."}

        return True, metrics

    def run_batch(
        self,
        items: list[BatchJobItem],
        skip_approved: bool = True,
        runner_fn: Optional[Callable[[BatchJobItem], dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Process batch jobs sequentially, respecting resource guards and resumability."""
        results: list[dict[str, Any]] = []
        completed = 0
        skipped = 0
        paused_or_blocked = 0
        failed = 0

        for item in items:
            try:
                project = self.project_mgr.get_project(item.project_id)
            except KeyError as exc:
                failed += 1
                results.append({
                    "project_id": item.project_id,
                    "batch_status": "FAILED",
                    "error": str(exc),
                    "error_category": ErrorCategory.INVALID_USER_INPUT.value,
                })
                continue

            if skip_approved and project.status in {ProjectStatus.APPROVED, ProjectStatus.EXPORTED}:
                skipped += 1
                results.append({
                    "project_id": item.project_id,
                    "chapter_title": project.chapter_title,
                    "batch_status": "SKIPPED_ALREADY_APPROVED",
                })
                continue

            ok_res, metrics = self.check_resource_guard()
            if not ok_res:
                paused_or_blocked += 1
                results.append({
                    "project_id": item.project_id,
                    "chapter_title": project.chapter_title,
                    "batch_status": "THROTTLED_RESOURCE_GUARD",
                    "metrics": metrics,
                })
                break  # Halt batch safely when host resources are constrained

            t0 = time.perf_counter()
            try:
                if runner_fn is not None:
                    out = runner_fn(item)
                else:
                    out = self.pipeline.run_staged(
                        project_id=item.project_id,
                        notes_files=item.notes_files,
                        typed_notes=item.typed_notes,
                        voice_path=item.voice_path,
                        ai_narration=item.ai_narration,
                    )
                duration = round(time.perf_counter() - t0, 2)
                status = out.get("status", "UNKNOWN")
                if status == ProjectStatus.WAITING_FOR_VOICE.value:
                    paused_or_blocked += 1
                elif status in {ProjectStatus.FAILED.value, "FAILED"}:
                    failed += 1
                else:
                    completed += 1
                results.append({
                    "project_id": item.project_id,
                    "chapter_title": project.chapter_title,
                    "batch_status": status,
                    "duration_sec": duration,
                    "output": out,
                })
            except Exception as exc:
                duration = round(time.perf_counter() - t0, 2)
                classified = classify_error(exc)
                failed += 1
                results.append({
                    "project_id": item.project_id,
                    "chapter_title": project.chapter_title,
                    "batch_status": "FAILED",
                    "duration_sec": duration,
                    "error": str(exc),
                    "error_category": classified.category.value,
                })

        return {
            "total_jobs": len(items),
            "completed": completed,
            "skipped": skipped,
            "paused_or_blocked": paused_or_blocked,
            "failed": failed,
            "results": results,
        }
