"""Resumable stage-level job manifest and safe temporary-file cleanup."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from upsc_studio.db.schemas import utc_now_iso


class JobManifestManager:
    """Tracks completed pipeline stages so failed renders never repeat academic research."""

    STAGES = (
        "ingestion",
        "syllabus",
        "research",
        "teaching",
        "storyboard",
        "graphics",
        "voice",
        "render",
        "qa",
    )

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.manifest_path = project_dir / "job_manifest.json"
        if not self.manifest_path.exists():
            self._save({s: {"status": "PENDING", "updated_at": None, "details": {}} for s in self.STAGES})

    def load(self) -> dict:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def is_stage_completed(self, stage: str) -> bool:
        data = self.load()
        return data.get(stage, {}).get("status") == "COMPLETED"

    def mark_stage(self, stage: str, status: str, details: dict | None = None) -> dict:
        data = self.load()
        data[stage] = {
            "status": status,
            "updated_at": utc_now_iso(),
            "details": details or {},
        }
        self._save(data)
        return data

    def cleanup_temp_files(self) -> int:
        """Remove transient upload staging files while preserving originals, raw voice, and final exports."""
        tmp_dir = self.project_dir / "inputs" / "uploads_tmp"
        removed = 0
        if tmp_dir.exists():
            for item in tmp_dir.iterdir():
                if item.is_file():
                    item.unlink()
                    removed += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    removed += 1
        return removed

    def _save(self, data: dict) -> None:
        self.manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
