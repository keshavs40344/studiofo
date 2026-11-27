"""10-Gate Quality Control auditor (Gates A through J) for final chapter-to-video certification."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from upsc_studio.db.schemas import SceneSpec
from upsc_studio.qa.auditor import QAAuditor
from upsc_studio.qa.completeness_audit import CompletenessAuditor


class TenGateAuditor:
    """Evaluates all 10 required quality gates transparently without hiding failures or treating PENDING as PASSED."""

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
    ) -> dict[str, Any]:
        base_qa = QAAuditor(self.conn, self.project_dir).run_all_checks(project_id, human_approved_by=human_approved_by)
        comp = (
            CompletenessAuditor(self.project_dir).audit_video(scenes, final_mp4)
            if final_mp4 and final_mp4.exists()
            else {"black_frame_segments_detected": -1, "scenes_audited": len(scenes)}
        )

        coverage_rows = self.conn.execute(
            "SELECT status FROM coverage_ledger WHERE project_id = ? ORDER BY id",
            (project_id,),
        ).fetchall()
        cov_count = len(coverage_rows)
        coverage_statuses = [str(row["status"]) for row in coverage_rows]
        unresolved_coverage = [
            status for status in coverage_statuses
            if status not in {"COVERED", "NOT_APPLICABLE"}
        ]
        external_sources = self.conn.execute(
            """
            SELECT COUNT(*) AS c FROM sources
            WHERE project_id = ?
              AND source_tier <> 'USER_NOTES'
              AND url IS NOT NULL
              AND TRIM(url) <> ''
            """,
            (project_id,),
        ).fetchone()["c"]
        source_count = self.conn.execute(
            "SELECT COUNT(*) AS c FROM sources WHERE project_id = ?", (project_id,)
        ).fetchone()["c"]

        # Gate evaluations - strictly require positive evidence
        has_subtitles = (self.project_dir / "subtitles" / "subtitles.srt").exists() and (
            (self.project_dir / "subtitles" / "subtitles.srt").stat().st_size > 0
        )
        final_video_valid = bool(
            final_mp4 and final_mp4.exists() and comp.get("black_frame_segments_detected") == 0
        )

        review_path = self.qa_dir / "manual_review.json"
        manual_review: dict[str, Any] = {}
        if review_path.is_file():
            try:
                manual_review = json.loads(review_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                manual_review = {}
        manual_checks = manual_review.get("checks", {})
        reviewer = str(manual_review.get("reviewer", "")).strip()
        has_human_reviewer = len(reviewer) >= 2
        reviewed = lambda key: has_human_reviewer and manual_checks.get(key) is True

        script_path = self.project_dir / "teaching" / "script_hinglish.md"
        outline_path = self.project_dir / "teaching" / "teaching_outline.md"
        teaching_files_present = all(
            path.is_file() and path.stat().st_size > 0
            for path in (script_path, outline_path)
        )
        visual_assets_present = bool(scenes) and all(
            scene.primary_asset and Path(scene.primary_asset).is_file()
            for scene in scenes
        )

        gates: dict[str, str] = {
            "A_SYLLABUS_COMPLETENESS": (
                "FAILED" if cov_count == 0 else ("PENDING" if unresolved_coverage else "PASSED")
            ),
            "B_RESEARCH_SOURCE": "PASSED" if external_sources > 0 else "FAILED",
            "C_FACTUAL_ACCURACY": base_qa["academic"]["status"],
            "D_SCRIPT_COMPLETENESS": (
                "PASSED" if script_path.is_file() and script_path.stat().st_size > 0 else "FAILED"
            ),
            "E_TEACHING_CLARITY": (
                "FAILED" if not teaching_files_present
                else ("PASSED" if reviewed("teaching_clarity") else "PENDING")
            ),
            "F_VISUAL_RELEVANCE": (
                "FAILED" if not visual_assets_present
                else ("PASSED" if reviewed("visual_relevance") else "PENDING")
            ),
            "G_VOICE_SUBTITLE_ALIGNMENT": (
                "FAILED" if not has_subtitles
                else ("PASSED" if reviewed("voice_subtitle_alignment") else "PENDING")
            ),
            "H_COPYRIGHT_LICENCE": base_qa["rights"]["status"],
            "I_AUDIO_VIDEO_TECHNICAL": base_qa["media"]["status"],
            "J_FINAL_PLAYBACK_INSPECTION": (
                "FAILED" if final_mp4 and comp.get("black_frame_segments_detected", -1) > 0
                else (
                    "PASSED" if final_video_valid and reviewed("final_playback_inspection")
                    else "PENDING"
                )
            ),
        }

        failed = [k for k, v in gates.items() if v == "FAILED"]
        pending = [k for k, v in gates.items() if v == "PENDING"]
        passed = [k for k, v in gates.items() if v == "PASSED"]

        # Ready for publication ONLY if all gates passed, none failed, none pending, and human approved
        ready_pub = (
            len(passed) == 10
            and len(failed) == 0
            and len(pending) == 0
            and base_qa["publication"]["status"] == "PASSED"
        )

        report = {
            "project_id": project_id,
            "gates": gates,
            "gate_details": {
                "A_SYLLABUS_COMPLETENESS": {
                    "coverage_rows": cov_count,
                    "unresolved_statuses": unresolved_coverage,
                },
                "B_RESEARCH_SOURCE": {
                    "source_rows": source_count,
                    "external_sources_with_url": external_sources,
                },
                "MANUAL_REVIEW": {
                    "reviewer": reviewer or None,
                    "reviewed_at": manual_review.get("reviewed_at"),
                    "checks": {
                        "teaching_clarity": reviewed("teaching_clarity"),
                        "visual_relevance": reviewed("visual_relevance"),
                        "voice_subtitle_alignment": reviewed("voice_subtitle_alignment"),
                        "final_playback_inspection": reviewed("final_playback_inspection"),
                    },
                },
            },
            "passed_gates": passed,
            "failed_gates": failed,
            "pending_gates": pending,
            "all_gates_passed": len(passed) == 10,
            "ready_for_publication": "PASSED" if ready_pub else "PENDING",
            "black_frame_segments_detected": comp.get("black_frame_segments_detected"),
        }
        (self.qa_dir / "final_10_gate_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        md = [
            "# Final 10-Gate Quality Control Report",
            "",
            *[f"- **{k}**: `{v}`" for k, v in gates.items()],
            "",
            f"- **PASSED GATES:** {len(passed)}/10",
            f"- **READY_FOR_PUBLICATION:** `{report['ready_for_publication']}`",
        ]
        (self.qa_dir / "final_10_gate_report.md").write_text("\n".join(md), encoding="utf-8")
        return report
