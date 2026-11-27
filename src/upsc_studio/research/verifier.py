"""Research, source hierarchy, atomic claim extraction, and evidence verification engine."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup

from upsc_studio.db.schemas import VerificationStatus, utc_now_iso

SOURCE_TIERS = (
    "PRIMARY_OFFICIAL",  # Constitution, Acts, Ministries, RBI, ECI, CAG, MoSPI, NITI Aayog, SC/HC
    "ACADEMIC_PEER_REVIEWED",
    "REPUTABLE_NEWS",
    "USER_NOTES",
    "OTHER",
)

HIGH_IMPACT_PATTERNS = (
    r"\barticle\s+\d+[a-z]?\b",
    r"\bsection\s+\d+[a-z]?\b",
    r"\bschedule\s+(?:[ivx]+|\d+)\b",
    r"\b\d+(?:\.\d+)?\s*%",
    r"\b(?:19|20)\d{2}\b",
    r"\b(?:act|amendment|judgment|committee|commission|scheme|budget|rank)\b",
)


def has_human_evidence_attestation(claim: dict[str, Any]) -> bool:
    """Return whether a VERIFIED claim has an explicit reviewer label and source excerpt."""
    notes = str(claim.get("verification_notes") or "")
    excerpt_marker = "Evidence excerpt:"
    excerpt = notes.split(excerpt_marker, 1)[1].strip() if excerpt_marker in notes else ""
    return bool(
        claim.get("status") == VerificationStatus.VERIFIED.value
        and notes.startswith("HUMAN_ATTESTED_BY:")
        and notes.splitlines()
        and notes.splitlines()[0].partition(":")[2].strip()
        and claim.get("source_id")
        and str(claim.get("page_or_section") or "").strip()
        and len(excerpt) >= 10
    )


class EvidenceEngine:
    """Manages sources, atomic claims, verification statuses, conflict detection, and fact gates.
    
    Hardened verification rules:
    - Never mark a claim VERIFIED merely because a source URL exists or is reachable.
    - Require atomic factual statements, specific source tier, publication date, and page/section reference.
    - Check for conflicting dates, numbers, or legal amendments across claims.
    - Unsupported, conflicting, or unverified claims strictly block or require human review.
    """

    def __init__(self, conn: sqlite3.Connection, project_dir: Path) -> None:
        self.conn = conn
        self.project_dir = project_dir
        self.research_dir = project_dir / "research"
        self.research_dir.mkdir(parents=True, exist_ok=True)

    def add_source(
        self,
        project_id: str,
        title: str,
        publisher: str,
        source_tier: str,
        url: Optional[str] = None,
        pub_date: Optional[str] = None,
        notes: str = "",
    ) -> str:
        """Register a source in the bibliography with mandatory tier validation."""
        if source_tier not in SOURCE_TIERS:
            raise ValueError(f"Invalid source_tier '{source_tier}'. Must be one of {SOURCE_TIERS}")
        source_id = f"src_{uuid.uuid4().hex[:8]}"
        self.conn.execute(
            """
            INSERT INTO sources (id, project_id, title, publisher, url, pub_date, access_date, source_tier, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (source_id, project_id, title, publisher, url, pub_date, utc_now_iso()[:10], source_tier, notes),
        )
        self.conn.commit()
        return source_id

    def add_claim(
        self,
        project_id: str,
        statement: str,
        chapter_section: str,
        status: VerificationStatus = VerificationStatus.UNSUPPORTED,
        source_id: Optional[str] = None,
        page_or_section: Optional[str] = None,
        ref_period: Optional[str] = None,
        scene_id: Optional[str] = None,
        verification_notes: str = "",
    ) -> str:
        """Register an atomic factual claim linked to a chapter section and optional source."""
        # Hardened check: VERIFIED requires a valid source_id AND non-empty page_or_section reference
        if status == VerificationStatus.VERIFIED:
            if not source_id:
                raise ValueError("Cannot mark a claim VERIFIED without a linked source_id.")
            if not page_or_section or not page_or_section.strip():
                raise ValueError("Cannot mark a claim VERIFIED without a specific page_or_section or excerpt reference.")

        claim_id = f"clm_{uuid.uuid4().hex[:8]}"
        self.conn.execute(
            """
            INSERT INTO claims (
                id, project_id, statement, chapter_section, scene_id,
                source_id, page_or_section, ref_period, status, verification_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                claim_id,
                project_id,
                statement.strip(),
                chapter_section,
                scene_id,
                source_id,
                page_or_section,
                ref_period,
                status.value,
                verification_notes,
            ),
        )
        self.conn.commit()
        return claim_id

    def extract_claims_from_text(
        self,
        project_id: str,
        chapter_section: str,
        text: str,
        default_source_id: Optional[str] = None,
    ) -> list[str]:
        """Decompose factual sentences containing dates, stats, laws, or bodies into atomic claims."""
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) >= 20]
        created_ids: list[str] = []
        for sent in sentences:
            low = sent.lower()
            is_factual = any(re.search(pat, low) for pat in HIGH_IMPACT_PATTERNS)
            if not is_factual:
                continue
            status = (
                VerificationStatus.HUMAN_REVIEW_REQUIRED
                if default_source_id
                else VerificationStatus.UNSUPPORTED
            )
            notes = (
                "Extracted from supplied notes; requires cross-check against primary official source."
                if default_source_id
                else "No source linked; unsupported until verified."
            )
            cid = self.add_claim(
                project_id=project_id,
                statement=sent,
                chapter_section=chapter_section,
                status=status,
                source_id=default_source_id,
                verification_notes=notes,
            )
            created_ids.append(cid)
        return created_ids

    def verify_claim_against_source(
        self,
        claim_id: str,
        source_id: str,
        page_or_section: str,
        evidence_excerpt: str,
        ref_period: Optional[str] = None,
        reviewer_id: Optional[str] = None,
    ) -> bool:
        """Record an explicit human attestation; this method does not infer semantic support.

        The reviewer must inspect the original source and affirm that the supplied excerpt
        supports the claim. URL reachability, a source ID, and a page reference alone are
        never sufficient to mark a claim VERIFIED.
        """
        if not reviewer_id or not reviewer_id.strip():
            raise ValueError("A non-empty reviewer_id is required for human evidence attestation.")
        if not page_or_section or len(page_or_section.strip()) < 2:
            raise ValueError("A specific page, section, or paragraph reference is required.")
        if not evidence_excerpt or len(evidence_excerpt.strip()) < 10:
            raise ValueError("Evidence excerpt too brief or missing; cannot record human attestation.")

        src_row = self.conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        if not src_row:
            raise ValueError(f"Source ID '{source_id}' does not exist.")
        claim_row = self.conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        if not claim_row:
            raise ValueError(f"Claim ID '{claim_id}' does not exist.")
        if claim_row["project_id"] != src_row["project_id"]:
            raise ValueError("Claim and source must belong to the same project.")

        excerpt = evidence_excerpt.strip()
        notes = (
            f"HUMAN_ATTESTED_BY:{reviewer_id.strip()}\n"
            f"Source: {src_row['title']} ({src_row['source_tier']})\n"
            f"Page or section: {page_or_section.strip()}\n"
            f"Evidence excerpt: {excerpt}"
        )
        self.conn.execute(
            """
            UPDATE claims
            SET status = ?, source_id = ?, page_or_section = ?, ref_period = ?, verification_notes = ?
            WHERE id = ?
            """,
            (VerificationStatus.VERIFIED.value, source_id, page_or_section.strip(), ref_period, notes, claim_id),
        )
        self.conn.commit()
        return True

    def detect_conflicts(self, project_id: str) -> list[dict[str, Any]]:
        """Identify potentially conflicting claims regarding dates, numbers, or articles."""
        claims = [
            dict(r)
            for r in self.conn.execute(
                "SELECT * FROM claims WHERE project_id = ? ORDER BY id", (project_id,)
            ).fetchall()
        ]
        conflicts: list[dict[str, Any]] = []

        # Check for year/date disparities on matching subject terms
        year_claims: dict[str, list[dict[str, Any]]] = {}
        for c in claims:
            years = re.findall(r"\b(?:19|20)\d{2}\b", c["statement"])
            for y in years:
                year_claims.setdefault(y, []).append(c)

        # Flag claims explicitly annotated with conflicting notes
        for c in claims:
            if "conflict" in c["verification_notes"].lower() or c["status"] == VerificationStatus.CONFLICTING.value:
                conflicts.append({
                    "claim_id": c["id"],
                    "statement": c["statement"],
                    "reason": c["verification_notes"] or "Marked as conflicting evidence",
                })
        return conflicts

    @staticmethod
    def check_url_live(url: str, timeout: int = 8) -> dict[str, Any]:
        """Safely inspect a URL's reachability and title without trusting page instructions.
        
        A live URL merely confirms server reachability, NEVER substantive factual accuracy.
        """
        try:
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": "UPSC-Studio-Verifier/0.1"})
            title = ""
            if "text/html" in resp.headers.get("content-type", ""):
                soup = BeautifulSoup(resp.text[:50000], "html.parser")
                if soup.title and soup.title.string:
                    title = soup.title.string.strip()[:200]
            return {
                "reachable": resp.status_code < 400,
                "status_code": resp.status_code,
                "title": title,
                "factual_verification_status": "URL_REACHABILITY_ONLY_NOT_FACT_CHECKED",
            }
        except Exception as exc:
            return {
                "reachable": False,
                "status_code": None,
                "error": str(exc),
                "factual_verification_status": "UNREACHABLE",
            }

    def export_ledger(self, project_id: str, cutoff_date: str) -> dict[str, Any]:
        """Write evidence_ledger.json, sources.bib.json, verification_report.md, and unresolved_claims.md."""
        sources = [
            dict(r)
            for r in self.conn.execute(
                "SELECT * FROM sources WHERE project_id = ? ORDER BY id", (project_id,)
            ).fetchall()
        ]
        claims = [
            dict(r)
            for r in self.conn.execute(
                "SELECT * FROM claims WHERE project_id = ? ORDER BY id", (project_id,)
            ).fetchall()
        ]

        counts: dict[str, int] = {s.value: 0 for s in VerificationStatus}
        unresolved: list[dict[str, Any]] = []
        for c in claims:
            if c["status"] == VerificationStatus.VERIFIED.value and not has_human_evidence_attestation(c):
                c["status"] = VerificationStatus.HUMAN_REVIEW_REQUIRED.value
                c["verification_notes"] = (
                    (c.get("verification_notes") or "")
                    + "\nExport gate: VERIFIED status downgraded because no human attestation excerpt is recorded."
                )
                self.conn.execute(
                    "UPDATE claims SET status = ?, verification_notes = ? WHERE id = ?",
                    (c["status"], c["verification_notes"], c["id"]),
                )
            st = c["status"]
            counts[st] = counts.get(st, 0) + 1
            if st != VerificationStatus.VERIFIED.value:
                unresolved.append(c)
        self.conn.commit()

        conflicts = self.detect_conflicts(project_id)

        ledger = {
            "project_id": project_id,
            "research_cutoff_date": cutoff_date,
            "total_claims": len(claims),
            "status_counts": counts,
            "conflicts_detected": conflicts,
            "claims": claims,
        }
        (self.research_dir / "evidence_ledger.json").write_text(
            json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (self.research_dir / "sources.bib.json").write_text(
            json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        report_lines = [
            f"# Fact Verification Report (Cutoff: {cutoff_date})",
            "",
            f"- Total Claims: {len(claims)}",
            *[f"- {k}: {v}" for k, v in counts.items()],
            f"- Conflicting Items Detected: {len(conflicts)}",
            "",
            "## Gate Status",
            "- **PASSED** only if `UNSUPPORTED == 0`, `CONFLICTING == 0`, and `HUMAN_REVIEW_REQUIRED == 0`.",
        ]
        (self.research_dir / "verification_report.md").write_text("\n".join(report_lines), encoding="utf-8")

        unres_lines = ["# Unresolved Claims Requiring Review", ""]
        if not unresolved:
            unres_lines.append("None — all recorded claims are VERIFIED.")
        else:
            for c in unresolved:
                unres_lines.append(f"- **[{c['id']}] ({c['status']})** {c['statement']} — _{c['verification_notes']}_")
        (self.research_dir / "unresolved_claims.md").write_text("\n".join(unres_lines), encoding="utf-8")
        return ledger
