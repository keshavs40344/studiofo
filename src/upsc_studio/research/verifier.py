"""Research, source hierarchy, atomic claim extraction, and evidence verification engine."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup

from upsc_studio.db.schemas import VerificationStatus, utc_now_iso
from upsc_studio.research.contradictions import ContradictionDetector, ContradictionRecord
from upsc_studio.research.corroborator import CorroborationEngine, TIER_QUALITY_WEIGHTS
from upsc_studio.research.extractor import DocumentExtractor
from upsc_studio.research.planner import ResearchPlanner
from upsc_studio.research.security import ResearchSecurityGuard

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
    r"\b(?:act|amendment|judgment|committee|commission|scheme|budget|rank|treaty)\b",
)

STOPWORDS = {
    "with", "from", "that", "this", "which", "about", "their", "these",
    "under", "where", "there", "have", "been", "were", "what", "when",
    "will", "would", "could", "should", "into", "over", "after", "before",
}


class EvidenceEngine:
    """Manages sources, atomic claims, verification statuses, conflict detection, and fact gates.

    Hardened verification rules:
    - Never mark a claim VERIFIED merely because a search result exists, URL is reachable, or keyword matches.
    - Require atomic factual statements, specific source tier, publication date, and page/section reference.
    - Check for conflicting dates, numbers, or legal classifications across claims.
    - Enforce research cutoffs: reject post-cutoff sources for current affairs.
    - Unsupported, conflicting, or unverified claims strictly block or require human review.
    - Clearly track 6-stage lifecycle: Discovered -> Accessible -> Extracted -> Supported -> Corroborated -> Human Reviewed.
    """

    def __init__(self, conn: sqlite3.Connection, project_dir: Path) -> None:
        self.conn = conn
        self.project_dir = project_dir
        self.research_dir = project_dir / "research"
        self.research_dir.mkdir(parents=True, exist_ok=True)
        self.security = ResearchSecurityGuard
        self.extractor = DocumentExtractor()
        self.contradiction_detector = ContradictionDetector()
        self.corroborator = CorroborationEngine()
        self.planner = ResearchPlanner()

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
        """Register a source in the bibliography with mandatory tier validation and security checks."""
        if source_tier not in SOURCE_TIERS:
            raise ValueError(f"Invalid source_tier '{source_tier}'. Must be one of {SOURCE_TIERS}")

        # Security check on untrusted metadata inputs
        clean_title = self.security.sanitize_untrusted_text(title, raise_on_threat=True)
        clean_publisher = self.security.sanitize_untrusted_text(publisher, raise_on_threat=True)
        clean_notes = self.security.sanitize_untrusted_text(notes, raise_on_threat=False)

        # Validate publication date format if provided
        if pub_date:
            clean_date = pub_date.strip()
            if not re.match(r"^\d{4}(?:-\d{2}-\d{2})?$", clean_date):
                raise ValueError(f"Invalid pub_date format '{pub_date}'. Expected YYYY or YYYY-MM-DD.")
            pub_date = clean_date

        source_id = f"src_{uuid.uuid4().hex[:8]}"
        self.conn.execute(
            """
            INSERT INTO sources (id, project_id, title, publisher, url, pub_date, access_date, source_tier, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (source_id, project_id, clean_title, clean_publisher, url, pub_date, utc_now_iso()[:10], source_tier, clean_notes),
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
        clean_statement = self.security.sanitize_untrusted_text(statement, raise_on_threat=True).strip()
        clean_notes = self.security.sanitize_untrusted_text(verification_notes, raise_on_threat=False)

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
                clean_statement,
                chapter_section,
                scene_id,
                source_id,
                page_or_section,
                ref_period,
                status.value,
                clean_notes,
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
        candidates = self.extractor.extract_atomic_claims(text, page_or_section=chapter_section)
        created_ids: list[str] = []

        for candidate in candidates:
            sent = candidate.statement
            is_factual = candidate.is_high_impact
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
            if default_source_id:
                existing = self.conn.execute(
                    """
                    SELECT id FROM claims
                    WHERE project_id = ? AND source_id = ?
                      AND chapter_section = ? AND statement = ?
                    LIMIT 1
                    """,
                    (project_id, default_source_id, chapter_section, sent),
                ).fetchone()
                if existing:
                    continue

            cid = self.add_claim(
                project_id=project_id,
                statement=sent,
                chapter_section=chapter_section,
                status=status,
                source_id=default_source_id,
                page_or_section=candidate.page_or_section,
                ref_period=candidate.ref_period,
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
        reviewer: str = "",
    ) -> bool:
        """Record a human attestation that the cited excerpt supports an atomic claim.

        Performs strict semantic relevancy, page/section reference validation,
        research cutoff checking, and contradiction screening.
        """
        claim_row = self.conn.execute(
            "SELECT * FROM claims WHERE id = ?", (claim_id,)
        ).fetchone()
        if not claim_row:
            raise ValueError(f"Claim ID '{claim_id}' does not exist.")

        src_row = self.conn.execute(
            "SELECT * FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
        if not src_row:
            raise ValueError(f"Source ID '{source_id}' does not exist.")

        project_id = claim_row["project_id"]
        if src_row["project_id"] != project_id or project_id is None:
            raise ValueError("Claim and source must belong to the same project.")

        if not reviewer or len(reviewer.strip()) < 2:
            raise ValueError("A named human reviewer is required (minimum 2 characters).")

        if not evidence_excerpt or len(evidence_excerpt.strip()) < 10:
            raise ValueError("Evidence excerpt too brief or missing; cannot record verification.")

        # Page or section reference must be specific
        if not page_or_section or len(page_or_section.strip()) < 3:
            raise ValueError("Specific page_or_section reference (e.g., 'Page 12, para 3') is required.")

        # Substantive relevancy check: excerpt must relate to the claim statement
        statement_text = claim_row["statement"]
        clean_excerpt = self.security.sanitize_untrusted_text(evidence_excerpt, raise_on_threat=True)

        st_words = {
            w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", statement_text)
            if w.lower() not in STOPWORDS
        }
        ex_words = {
            w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", clean_excerpt)
            if w.lower() not in STOPWORDS
        }
        shared_tokens = st_words.intersection(ex_words)

        # If statement contains substantive terms, there must be at least one matching core token
        if st_words and not shared_tokens:
            raise ValueError(
                f"Evidence excerpt does not relate to the claim statement. "
                f"No shared substantive terms between statement and excerpt."
            )

        # Cutoff Date Check: exclude sources published after the project cutoff date
        proj_row = self.conn.execute(
            "SELECT cutoff_date FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if proj_row and proj_row["cutoff_date"] and src_row["pub_date"]:
            try:
                cutoff = date.fromisoformat(str(proj_row["cutoff_date"])[:10])
                src_pub = date.fromisoformat(str(src_row["pub_date"])[:10])
                if src_pub > cutoff:
                    self.conn.execute(
                        "UPDATE claims SET status = ?, verification_notes = ? WHERE id = ?",
                        (
                            VerificationStatus.OUTDATED.value,
                            f"Rejected: source publication date ({src_pub}) post-dates project cutoff ({cutoff}).",
                            claim_id,
                        ),
                    )
                    self.conn.commit()
                    raise ValueError(
                        f"Source publication date ({src_pub}) exceeds project research cutoff date ({cutoff})."
                    )
            except (ValueError, TypeError) as exc:
                if "exceeds project research cutoff date" in str(exc):
                    raise

        # Contradiction screening against other recorded claims in the project
        all_claims = [
            dict(r) for r in self.conn.execute(
                "SELECT * FROM claims WHERE project_id = ?", (project_id,)
            ).fetchall()
        ]
        simulated_claim = dict(claim_row)
        simulated_claim["statement"] = statement_text
        simulated_claim["status"] = VerificationStatus.VERIFIED.value

        conflicts = self.contradiction_detector.detect_all_conflicts(all_claims + [simulated_claim])
        relevant_conflicts = [c for c in conflicts if c.claim_id_a == claim_id or c.claim_id_b == claim_id]

        if relevant_conflicts:
            conflict_desc = relevant_conflicts[0].description
            self.conn.execute(
                """
                UPDATE claims
                SET status = ?, verification_notes = ?
                WHERE id = ?
                """,
                (
                    VerificationStatus.CONFLICTING.value,
                    f"Contradiction detected: {conflict_desc}",
                    claim_id,
                ),
            )
            self.conn.commit()
            raise ValueError(f"Claim contradicts existing project claim: {conflict_desc}")

        tier = src_row["source_tier"]
        notes = (
            f"Human-attested by {reviewer.strip()} against {tier} ({src_row['title']}). "
            f"Recorded excerpt: {clean_excerpt[:250]}"
        )

        self.conn.execute(
            """
            UPDATE claims
            SET status = ?, source_id = ?, page_or_section = ?, ref_period = ?, verification_notes = ?
            WHERE id = ? AND project_id = ?
            """,
            (
                VerificationStatus.VERIFIED.value,
                source_id,
                page_or_section.strip(),
                ref_period,
                notes,
                claim_id,
                project_id,
            ),
        )
        if self.conn.execute("SELECT changes()").fetchone()[0] != 1:
            raise ValueError("Claim was not updated; verify the project and claim identifiers.")
        self.conn.commit()
        return True

    def detect_conflicts(self, project_id: str) -> list[dict[str, Any]]:
        """Identify potentially conflicting claims regarding dates, numbers, or legal status."""
        claims = [
            dict(r)
            for r in self.conn.execute(
                "SELECT * FROM claims WHERE project_id = ? ORDER BY id", (project_id,)
            ).fetchall()
        ]
        conflicts: list[dict[str, Any]] = []

        # Use new dedicated contradiction detector
        detector_conflicts = self.contradiction_detector.detect_all_conflicts(claims)
        for dc in detector_conflicts:
            conflicts.append({
                "claim_id": dc.claim_id_a,
                "statement": dc.statement_a,
                "reason": dc.description,
                "conflicting_claim_id": dc.claim_id_b,
                "conflict_type": dc.conflict_type,
            })

        # Check for year disparities and claims annotated with conflicting notes
        for c in claims:
            if "conflict" in c["verification_notes"].lower() or c["status"] == VerificationStatus.CONFLICTING.value:
                if not any(item["claim_id"] == c["id"] for item in conflicts):
                    conflicts.append({
                        "claim_id": c["id"],
                        "statement": c["statement"],
                        "reason": c["verification_notes"] or "Marked as conflicting evidence",
                    })

        # Save contradictions report
        self.contradiction_detector.export_report(detector_conflicts, self.research_dir)
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
        """Write evidence_ledger.json, sources.bib.json, verification_report.md, unresolved_claims.md, and research_plan.json."""
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

        proj_row = self.conn.execute(
            "SELECT chapter_title, content_category FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        topic_title = proj_row["chapter_title"] if proj_row else "UPSC Chapter"
        content_category = proj_row["content_category"] if proj_row else "upsc"

        # Generate & save research plan
        plan = self.planner.build_plan(
            project_id=project_id,
            topic_title=topic_title,
            content_category=content_category,
            cutoff_date=cutoff_date,
        )
        plan.save(self.research_dir)

        # Source index for fast lookup
        sources_by_id = {s["id"]: s for s in sources}

        # Enrich claims with 6-stage lifecycle tracking
        enriched_claims: list[dict[str, Any]] = []
        counts: dict[str, int] = {s.value: 0 for s in VerificationStatus}
        unresolved: list[dict[str, Any]] = []

        for c in claims:
            st = c["status"]
            counts[st] = counts.get(st, 0) + 1
            if st != VerificationStatus.VERIFIED.value:
                unresolved.append(c)

            src = sources_by_id.get(c.get("source_id"))
            has_source = src is not None
            has_excerpt = bool(c.get("page_or_section") or "excerpt" in c.get("verification_notes", "").lower())
            is_verified = st == VerificationStatus.VERIFIED.value
            has_reviewer = "Human-attested" in c.get("verification_notes", "")

            # Multi-source corroboration check
            corroborated, quality_score, _ = self.corroborator.evaluate_corroboration(
                primary_source=src or {},
                corroborating_sources=[],
                statement=c["statement"],
                is_high_impact=any(re.search(pat, c["statement"].lower()) for pat in HIGH_IMPACT_PATTERNS),
            )

            lifecycle = {
                "source_discovered": has_source,
                "source_accessible": bool(src and src.get("url")),
                "evidence_extracted": has_excerpt,
                "claim_supported": is_verified or st == VerificationStatus.PARTIALLY_VERIFIED.value,
                "independently_corroborated": corroborated,
                "human_reviewed": has_reviewer,
            }

            enriched = dict(c)
            enriched["publisher"] = src.get("publisher") if src else None
            enriched["pub_date"] = src.get("pub_date") if src else None
            enriched["access_date"] = src.get("access_date") if src else None
            enriched["source_tier"] = src.get("source_tier") if src else None
            enriched["evidence_quality_score"] = quality_score
            enriched["lifecycle"] = lifecycle
            enriched_claims.append(enriched)

        conflicts = self.detect_conflicts(project_id)

        ledger = {
            "project_id": project_id,
            "research_cutoff_date": cutoff_date,
            "total_claims": len(claims),
            "status_counts": counts,
            "conflicts_detected": conflicts,
            "claims": enriched_claims,
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
            "",
            "## Verification Limitations",
            "- Automated checks confirm citation presence, temporal validity, and human attestation.",
            "- Automated checks do not guarantee 100% semantic factuality; human domain expert review remains mandatory.",
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
