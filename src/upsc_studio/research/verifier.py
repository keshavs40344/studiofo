"""Research, source hierarchy, and claim-level fact-verification engine."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from upsc_studio.db.schemas import VerificationStatus, utc_now_iso

SOURCE_TIERS = (
    "PRIMARY_OFFICIAL",      # Constitution, India Code, Ministries, RBI, ECI, CAG, MoSPI, NITI Aayog, SC/HC
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


class EvidenceEngine:
    """Manages sources, atomic claims, verification statuses, and fact gates."""

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
        """Register a source in the bibliography."""
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
        if status == VerificationStatus.VERIFIED and not source_id:
            raise ValueError("Cannot mark a claim VERIFIED without a linked source_id.")
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
        """Decompose factual sentences containing dates, stats, laws, or bodies into claims."""
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

    @staticmethod
    def check_url_live(url: str, timeout: int = 8) -> dict:
        """Safely inspect a URL's reachability and title without trusting page instructions."""
        try:
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": "UPSC-Studio-Verifier/0.1"})
            title = ""
            if "text/html" in resp.headers.get("content-type", ""):
                soup = BeautifulSoup(resp.text[:50000], "html.parser")
                if soup.title and soup.title.string:
                    title = soup.title.string.strip()[:200]
            return {"reachable": resp.status_code < 400, "status_code": resp.status_code, "title": title}
        except Exception as exc:
            return {"reachable": False, "status_code": None, "error": str(exc)}

    def export_ledger(self, project_id: str, cutoff_date: str) -> dict:
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
        unresolved: list[dict] = []
        for c in claims:
            st = c["status"]
            counts[st] = counts.get(st, 0) + 1
            if st != VerificationStatus.VERIFIED.value:
                unresolved.append(c)

        ledger = {
            "project_id": project_id,
            "research_cutoff_date": cutoff_date,
            "total_claims": len(claims),
            "status_counts": counts,
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
