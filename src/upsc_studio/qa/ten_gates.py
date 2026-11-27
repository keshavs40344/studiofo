"""10-Gate Quality Control auditor (Gates A through J) for final chapter-to-video certification."""

from __future__ import annotations

import hashlib
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

    def review_fingerprint(
        self,
        project_id: str,
        scenes: list[SceneSpec],
        final_mp4: Path | None,
    ) -> str:
        """Bind manual review to the exact script, scenes, media, subtitles and research rows."""
        files: dict[str, Any] = {}

        def add_file(path: Path) -> None:
            resolved = Path(path)
            try:
                label = resolved.resolve().relative_to(self.project_dir.resolve()).as_posix()
            except ValueError:
                label = resolved.name
            if resolved.is_file():
                digest = hashlib.sha256()
                with resolved.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                files[label] = {"exists": True, "size": resolved.stat().st_size, "sha256": digest.hexdigest()}
            else:
                files[label] = {"exists": False}

        for relative in (
            "teaching/script_hinglish.md",
            "teaching/teaching_outline.md",
            "storyboard/storyboard.json",
            "subtitles/subtitles.srt",
        ):
            add_file(self.project_dir / relative)
        video = final_mp4 or (self.project_dir / "render" / "final" / "final_video.mp4")
        add_file(video)
        for folder in (self.project_dir / "audio" / "processed",):
            if folder.is_dir():
                for path in sorted(item for item in folder.rglob("*") if item.is_file()):
                    add_file(path)
        for scene in scenes:
            for asset in (scene.primary_asset, scene.supporting_asset):
                if asset:
                    add_file(Path(asset))

        claims = [
            dict(row) for row in self.conn.execute(
                """
                SELECT id, statement, source_id, status, verification_notes
                FROM claims WHERE project_id = ? ORDER BY id
                """,
                (project_id,),
            ).fetchall()
        ]
        sources = [
            dict(row) for row in self.conn.execute(
                """
                SELECT id, title, publisher, url, pub_date, source_tier
                FROM sources WHERE project_id = ? ORDER BY id
                """,
                (project_id,),
            ).fetchall()
        ]
        coverage = [
            dict(row) for row in self.conn.execute(
                """
                SELECT syllabus_item_id, status, reason
                FROM coverage_ledger WHERE project_id = ? ORDER BY id
                """,
                (project_id,),
            ).fetchall()
        ]
        canonical = json.dumps(
            {"files": files, "claims": claims, "sources": sources, "coverage": coverage},
            sort_keys=True, ensure_ascii=False, default=str,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

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

        project_row = self.conn.execute(
            "SELECT content_category FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        content_category = project_row["content_category"] if project_row else "upsc"
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
        topic_map_path = self.project_dir / "research" / "topic_map.json"
        topic_map_exists = topic_map_path.is_file()
        topic_map = {}
        if topic_map_exists:
            try:
                topic_map = json.loads(topic_map_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                topic_map = {}
        topic_map_valid = (
            isinstance(topic_map.get("topics"), list)
            and len(topic_map["topics"]) > 0
            and topic_map.get("content_category") == content_category
        )
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
        current_review_fingerprint = self.review_fingerprint(project_id, scenes, final_mp4)
        review_is_current = manual_review.get("artifact_fingerprint") == current_review_fingerprint
        has_human_reviewer = len(reviewer) >= 2 and review_is_current
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
                "FAILED" if content_category == "upsc" and cov_count == 0
                else (
                    "PENDING" if content_category == "upsc" and unresolved_coverage
                    else (
                        "PENDING" if content_category != "upsc" and not topic_map_valid
                        else ("PASSED" if reviewed("content_scope_coverage") else "PENDING")
                    )
                )
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
                "CONTENT_SCOPE": {
                    "category": content_category,
                    "upsc_coverage_rows": cov_count,
                    "upsc_unresolved_statuses": unresolved_coverage,
                    "topic_map_exists": topic_map_exists,
                    "topic_map_valid": topic_map_valid,
                },
                "MANUAL_REVIEW": {
                    "reviewer": reviewer or None,
                    "reviewed_at": manual_review.get("reviewed_at"),
                    "review_is_current": review_is_current,
                    "checks": {
                        "content_scope_coverage": reviewed("content_scope_coverage"),
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
