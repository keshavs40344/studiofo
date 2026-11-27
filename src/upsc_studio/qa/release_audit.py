"""Automated end-to-end release readiness & compliance report generator.

Generates `qa/release_candidate.json` and `qa/release_report.md` aggregating
the four independent QA gates, 10-gate breakdown, artifact checksums, and
unresolved blockers without collapsing distinct gates into one misleading score.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from upsc_studio.core.paths import sha256_file
from upsc_studio.db.schemas import QAGateName, SceneSpec
from upsc_studio.qa.auditor import QAAuditor
from upsc_studio.qa.ten_gates import TenGateAuditor


class ReleaseAuditGenerator:
    """Produces auditable release candidate manifests and markdown reports."""

    def __init__(self, conn: sqlite3.Connection, project_dir: Path) -> None:
        self.conn = conn
        self.project_dir = Path(project_dir).resolve()
        self.qa_dir = self.project_dir / "qa"
        self.qa_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        project_id: str,
        scenes: list[SceneSpec] | None = None,
        final_video: Path | None = None,
    ) -> dict[str, Any]:
        """Compile release_candidate.json and release_report.md."""
        project_row = self.conn.execute(
            "SELECT id, name, chapter_title, content_category, status, cutoff_date FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if not project_row:
            raise KeyError(f"Project not found: {project_id}")

        if scenes is None:
            sb_path = self.project_dir / "storyboard" / "storyboard.json"
            if sb_path.is_file():
                raw = json.loads(sb_path.read_text(encoding="utf-8"))
                scenes = [SceneSpec.model_validate(s) for s in raw]
            else:
                scenes = []

        if final_video is None:
            candidate_mp4 = self.project_dir / "render" / "final" / "final_video.mp4"
            final_video = candidate_mp4 if candidate_mp4.is_file() else None

        qa_summary = QAAuditor(self.conn, self.project_dir).run_all_checks(project_id)
        ten_gates = TenGateAuditor(self.conn, self.project_dir).run_ten_gates(
            project_id, scenes, final_video
        )

        # Separate the four required release gates explicitly
        gate_statuses = {
            QAGateName.ACADEMICALLY_REVIEWED.value: qa_summary.get("academic", {}).get("status", "FAILED"),
            QAGateName.RIGHTS_CLEARED.value: qa_summary.get("rights", {}).get("status", "FAILED"),
            QAGateName.VIDEO_TECHNICALLY_APPROVED.value: qa_summary.get("media", {}).get("status", "FAILED"),
            QAGateName.READY_FOR_PUBLICATION.value: ten_gates.get("ready_for_publication", "FAILED"),
        }

        # Artifact checksums for traceability
        artifacts: dict[str, Any] = {}
        tracked_files = [
            ("script_hinglish", self.project_dir / "teaching" / "script_hinglish.md"),
            ("storyboard", self.project_dir / "storyboard" / "storyboard.json"),
            ("subtitles_srt", self.project_dir / "subtitles" / "subtitles.srt"),
            ("final_video", final_video),
        ]
        for label, fpath in tracked_files:
            if fpath and Path(fpath).is_file():
                p = Path(fpath)
                artifacts[label] = {
                    "path": str(p),
                    "size_bytes": p.stat().st_size,
                    "sha256": sha256_file(p),
                }
            else:
                artifacts[label] = None

        blockers = list(ten_gates.get("failed_gates", [])) + list(ten_gates.get("pending_gates", []))

        candidate = {
            "schema_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project": {
                "id": project_row[0],
                "name": project_row[1],
                "chapter_title": project_row[2],
                "content_category": project_row[3],
                "status": project_row[4],
                "cutoff_date": project_row[5],
            },
            "core_gates": gate_statuses,
            "ten_gates_summary": {
                "ready_for_publication": ten_gates.get("ready_for_publication"),
                "failed_gates": ten_gates.get("failed_gates", []),
                "pending_gates": ten_gates.get("pending_gates", []),
                "gates": ten_gates.get("gates", {}),
            },
            "qa_details": qa_summary,
            "artifacts": artifacts,
            "blocking_issues": blockers,
            "public_upload_authorized": gate_statuses[QAGateName.READY_FOR_PUBLICATION.value] == "PASSED",
        }

        json_path = self.qa_dir / "release_candidate.json"
        json_path.write_text(json.dumps(candidate, indent=2, ensure_ascii=False), encoding="utf-8")

        md_lines = [
            f"# Release Candidate Report — {project_row[2]}",
            "",
            f"- **Project ID:** `{project_id}`",
            f"- **Category:** `{project_row[3]}`",
            f"- **Generated At:** `{candidate['generated_at']}`",
            f"- **Public Upload Authorized:** `{candidate['public_upload_authorized']}`",
            "",
            "## 1. Core QA Gates (Separated)",
            "",
            f"- **ACADEMICALLY_REVIEWED:** `{gate_statuses[QAGateName.ACADEMICALLY_REVIEWED.value]}`",
            f"- **RIGHTS_CLEARED:** `{gate_statuses[QAGateName.RIGHTS_CLEARED.value]}`",
            f"- **VIDEO_TECHNICALLY_APPROVED:** `{gate_statuses[QAGateName.VIDEO_TECHNICALLY_APPROVED.value]}`",
            f"- **READY_FOR_PUBLICATION:** `{gate_statuses[QAGateName.READY_FOR_PUBLICATION.value]}`",
            "",
            "## 2. Tracked Release Artifacts",
            "",
        ]
        for label, meta in artifacts.items():
            if meta:
                md_lines.append(f"- **{label}:** `{meta['path']}` ({meta['size_bytes']} bytes, `sha256:{meta['sha256'][:12]}...`)")
            else:
                md_lines.append(f"- **{label}:** `MISSING`")

        md_lines.extend(["", "## 3. Blocking Issues", ""])
        if blockers:
            for b in blockers:
                md_lines.append(f"- `{b}`")
        else:
            md_lines.append("- None. All automated and manual gates passed.")

        md_path = self.qa_dir / "release_report.md"
        md_path.write_text("\n".join(md_lines), encoding="utf-8")

        return {
            "release_candidate_json": str(json_path),
            "release_report_md": str(md_path),
            "candidate": candidate,
        }
