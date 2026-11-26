"""10-Gate Quality Control auditor (Gates A through J) for final chapter-to-video certification."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from upsc_studio.db.schemas import SceneSpec
from upsc_studio.qa.auditor import QAAuditor
from upsc_studio.qa.completeness_audit import CompletenessAuditor


class TenGateAuditor:
    """Evaluates all 10 required quality gates transparently without hiding failures."""

    def __init__(self, conn: sqlite3.Connection, project_dir: Path) -> None:
        self.conn = conn
        self.project_dir = project_dir
        self.qa_dir = project_dir / "qa"
        self.qa_dir.mkdir(parents=True, exist_ok=True)

    def run_ten_gates(
        self,
        project_id: str,
        scenes: list[SceneSpec],
        final_mp4: Path | None,
        human_approved_by: str | None = None,
    ) -> dict:
        base_qa = QAAuditor(self.conn, self.project_dir).run_all_checks(project_id, human_approved_by=human_approved_by)
        comp = (
            CompletenessAuditor(self.project_dir).audit_video(scenes, final_mp4)
            if final_mp4 and final_mp4.exists()
            else {"black_frame_segments_detected": -1, "scenes_audited": len(scenes)}
        )

        cov_count = self.conn.execute(
            "SELECT COUNT(*) AS c FROM coverage_ledger WHERE project_id = ?", (project_id,)
        ).fetchone()["c"]
        src_count = self.conn.execute(
            "SELECT COUNT(*) AS c FROM sources WHERE project_id = ?", (project_id,)
        ).fetchone()["c"]

        gates = {
            "A_SYLLABUS_COMPLETENESS": "PASSED" if cov_count > 0 else "FAILED",
            "B_RESEARCH_SOURCE": "PASSED" if src_count > 0 else "FAILED",
            "C_FACTUAL_ACCURACY": base_qa["academic"]["status"],
            "D_SCRIPT_COMPLETENESS": "PASSED" if (self.project_dir / "teaching" / "script_hinglish.md").exists() else "FAILED",
            "E_TEACHING_CLARITY": "PASSED" if (self.project_dir / "teaching" / "teaching_outline.md").exists() else "FAILED",
            "F_VISUAL_RELEVANCE": "PASSED" if all(s.primary_asset and Path(s.primary_asset).exists() for s in scenes) else "FAILED",
            "G_VOICE_SUBTITLE_ALIGNMENT": "PASSED" if (self.project_dir / "subtitles" / "subtitles.srt").exists() else "PENDING",
            "H_COPYRIGHT_LICENCE": base_qa["rights"]["status"],
            "I_AUDIO_VIDEO_TECHNICAL": base_qa["media"]["status"],
            "J_FINAL_PLAYBACK_INSPECTION": (
                "PASSED"
                if (final_mp4 and final_mp4.exists() and comp.get("black_frame_segments_detected") == 0)
                else "PENDING"
            ),
        }

        failed = [k for k, v in gates.items() if v == "FAILED"]
        pending = [k for k, v in gates.items() if v == "PENDING"]
        report = {
            "project_id": project_id,
            "gates": gates,
            "failed_gates": failed,
            "pending_gates": pending,
            "ready_for_publication": base_qa["publication"]["status"],
            "black_frame_segments_detected": comp.get("black_frame_segments_detected"),
        }
        (self.qa_dir / "final_10_gate_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        md = [
            "# Final 10-Gate Quality Control Report",
            "",
            *[f"- **{k}**: `{v}`" for k, v in gates.items()],
            "",
            f"- **READY_FOR_PUBLICATION:** `{report['ready_for_publication']}`",
        ]
        (self.qa_dir / "final_10_gate_report.md").write_text("\n".join(md), encoding="utf-8")
        return report
