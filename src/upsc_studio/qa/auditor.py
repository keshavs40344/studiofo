"""Academic, Rights, Media/Export QA auditor with separate release gates."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import uuid
from pathlib import Path

from upsc_studio.core.hardware import find_ffmpeg
from upsc_studio.db.schemas import QAGateName, QAGateStatus, VerificationStatus, utc_now_iso
from upsc_studio.graphics.rights import AssetRightsLedger


class QAAuditor:
    """Evaluates academic, rights, and technical media gates separately."""

    def __init__(self, conn: sqlite3.Connection, project_dir: Path) -> None:
        self.conn = conn
        self.project_dir = project_dir
        self.qa_dir = project_dir / "qa"
        self.qa_dir.mkdir(parents=True, exist_ok=True)

    def run_all_checks(self, project_id: str, human_approved_by: str | None = None) -> dict:
        """Run Academic, Rights, and Video Technical QA and write reports."""
        academic = self._check_academic(project_id)
        rights = self._check_rights(project_id)
        media = self._check_media(project_id)

        all_subgates_passed = (
            academic["status"] == QAGateStatus.PASSED.value
            and rights["status"] == QAGateStatus.PASSED.value
            and media["status"] == QAGateStatus.PASSED.value
        )
        pub_blockers: list[str] = []
        if not all_subgates_passed:
            pub_blockers.append("One or more prerequisite QA gates (Academic, Rights, Video Technical) failed.")
        if not human_approved_by:
            pub_blockers.append("Final human publication approval not yet recorded.")

        pub_status = QAGateStatus.PASSED.value if not pub_blockers else QAGateStatus.PENDING.value
        publication = {
            "gate": QAGateName.READY_FOR_PUBLICATION.value,
            "status": pub_status,
            "blocking_issues": pub_blockers,
            "approved_by": human_approved_by,
        }

        self._persist_gate(project_id, QAGateName.ACADEMICALLY_REVIEWED, academic["status"], academic["blocking_issues"], None)
        self._persist_gate(project_id, QAGateName.RIGHTS_CLEARED, rights["status"], rights["blocking_issues"], None)
        self._persist_gate(project_id, QAGateName.VIDEO_TECHNICALLY_APPROVED, media["status"], media["blocking_issues"], None)
        self._persist_gate(project_id, QAGateName.READY_FOR_PUBLICATION, pub_status, pub_blockers, human_approved_by)

        (self.qa_dir / "academic_qa.json").write_text(json.dumps(academic, indent=2), encoding="utf-8")
        (self.qa_dir / "rights_qa.json").write_text(json.dumps(rights, indent=2), encoding="utf-8")
        (self.qa_dir / "media_qa.json").write_text(json.dumps(media, indent=2), encoding="utf-8")

        md = [
            "# Release Readiness Report",
            "",
            f"- **ACADEMICALLY_REVIEWED:** `{academic['status']}` (Blockers: {len(academic['blocking_issues'])})",
            f"- **RIGHTS_CLEARED:** `{rights['status']}` (Blockers: {len(rights['blocking_issues'])})",
            f"- **VIDEO_TECHNICALLY_APPROVED:** `{media['status']}` (Blockers: {len(media['blocking_issues'])})",
            f"- **READY_FOR_PUBLICATION:** `{publication['status']}`",
            "",
            "## Blocking Issues",
        ]
        for grp in (academic, rights, media, publication):
            for issue in grp["blocking_issues"]:
                md.append(f"- [{grp['gate']}] {issue}")
        if not any(g["blocking_issues"] for g in (academic, rights, media, publication)):
            md.append("- None.")
        (self.qa_dir / "release_readiness.md").write_text("\n".join(md), encoding="utf-8")

        return {
            "academic": academic,
            "rights": rights,
            "media": media,
            "publication": publication,
        }

    def _check_academic(self, project_id: str) -> dict:
        blockers: list[str] = []
        project_row = self.conn.execute(
            "SELECT content_category FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        content_category = project_row["content_category"] if project_row else "upsc"
        cov_rows = self.conn.execute(
            "SELECT status FROM coverage_ledger WHERE project_id = ?", (project_id,)
        ).fetchall()
        if content_category == "upsc" and not cov_rows:
            blockers.append("No UPSC syllabus coverage mapping recorded.")
        elif content_category != "upsc":
            topic_map_path = self.project_dir / "research" / "topic_map.json"
            if not topic_map_path.is_file():
                blockers.append("Category topic map is missing.")

        claims = self.conn.execute(
            """
            SELECT c.id, c.status, c.source_id, s.source_tier, s.url
            FROM claims AS c
            LEFT JOIN sources AS s ON s.id = c.source_id
            WHERE c.project_id = ?
            ORDER BY c.id
            """,
            (project_id,),
        ).fetchall()
        if not claims:
            blockers.append("No factual claims have been entered for academic review.")
        bad_claims = [c["id"] for c in claims if c["status"] != VerificationStatus.VERIFIED.value]
        if bad_claims:
            blockers.append(f"{len(bad_claims)} claim(s) are not VERIFIED: {', '.join(bad_claims[:5])}")

        claims_without_external_source = [
            c["id"] for c in claims
            if c["status"] == VerificationStatus.VERIFIED.value
            and (
                not c["source_id"]
                or not c["source_tier"]
                or c["source_tier"] == "USER_NOTES"
                or not c["url"]
                or not str(c["url"]).strip()
            )
        ]
        if claims_without_external_source:
            blockers.append(
                "Verified claims without an external source URL: "
                + ", ".join(claims_without_external_source[:5])
            )

        external_source_count = self.conn.execute(
            """
            SELECT COUNT(*) AS c FROM sources
            WHERE project_id = ?
              AND source_tier <> 'USER_NOTES'
              AND url IS NOT NULL
              AND TRIM(url) <> ''
            """,
            (project_id,),
        ).fetchone()["c"]
        if external_source_count == 0:
            blockers.append("No non-user research source with a URL is recorded.")

        common_required_files = (
            "teaching/script_hinglish.md",
            "teaching/study_notes.md",
            "teaching/question_bank.json",
        )
        category_required_files = (
            ("teaching/prelims_track.md", "teaching/mains_track.md")
            if content_category == "upsc"
            else ("teaching/topic_context.md", "teaching/analysis_framework.md")
        )
        for req_file in (*common_required_files, *category_required_files):
            target = self.project_dir / req_file
            if not target.is_file() or target.stat().st_size == 0:
                blockers.append(f"Missing required teaching deliverable: {req_file}")

        return {
            "gate": QAGateName.ACADEMICALLY_REVIEWED.value,
            "status": QAGateStatus.PASSED.value if not blockers else QAGateStatus.FAILED.value,
            "blocking_issues": blockers,
        }

    def _check_rights(self, project_id: str) -> dict:
        ledger = AssetRightsLedger(self.conn, self.project_dir)
        unverified = ledger.find_unverified_assets(project_id)
        blockers = [f"Asset {a['id']} ({a['file_path']}) has rights status {a['rights_status']}" for a in unverified]
        all_assets = ledger.export_manifest(project_id)
        if not all_assets:
            blockers.append("No assets registered in rights ledger.")
        return {
            "gate": QAGateName.RIGHTS_CLEARED.value,
            "status": QAGateStatus.PASSED.value if not blockers else QAGateStatus.FAILED.value,
            "blocking_issues": blockers,
        }

    def _check_media(self, project_id: str) -> dict:
        blockers: list[str] = []
        final_mp4 = self.project_dir / "render" / "final" / "final_video.mp4"
        srt_file = self.project_dir / "subtitles" / "subtitles.srt"
        audio_qa_file = self.project_dir / "audio" / "processed" / "audio_qa.json"

        if not final_mp4.exists() or final_mp4.stat().st_size == 0:
            blockers.append("Final rendered MP4 is missing or empty.")
        else:
            ffmpeg_exe = find_ffmpeg()
            if ffmpeg_exe:
                probe = subprocess.run(
                    [ffmpeg_exe, "-i", str(final_mp4)],
                    capture_output=True,
                    text=True,
                )
                info = probe.stderr or ""
                if "Video:" not in info:
                    blockers.append("Final MP4 has no detectable Video stream.")
                if "Audio:" not in info:
                    blockers.append("Final MP4 has no detectable Audio stream.")

        if not srt_file.exists() or not srt_file.read_text(encoding="utf-8").strip():
            blockers.append("Subtitles SRT file is missing or empty.")

        if not audio_qa_file.exists():
            blockers.append("Audio QA report missing (narration not processed).")
        else:
            audio_qa = json.loads(audio_qa_file.read_text(encoding="utf-8"))
            if audio_qa.get("clipping_detected"):
                blockers.append("Audio clipping detected in processed narration.")
            if not audio_qa.get("intelligible_level"):
                blockers.append("Audio mean volume is too low for intelligible narration.")

        return {
            "gate": QAGateName.VIDEO_TECHNICALLY_APPROVED.value,
            "status": QAGateStatus.PASSED.value if not blockers else QAGateStatus.FAILED.value,
            "blocking_issues": blockers,
        }

    def _persist_gate(
        self,
        project_id: str,
        gate: QAGateName,
        status: str,
        blockers: list[str],
        approved_by: str | None,
    ) -> None:
        self.conn.execute(
            "DELETE FROM qa_gates WHERE project_id = ? AND gate_name = ?",
            (project_id, gate.value),
        )
        self.conn.execute(
            """
            INSERT INTO qa_gates (id, project_id, gate_name, status, blocking_issues_json, checked_at, approved_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"qa_{uuid.uuid4().hex[:8]}",
                project_id,
                gate.value,
                status,
                json.dumps(blockers),
                utc_now_iso(),
                approved_by,
            ),
        )
        self.conn.commit()
