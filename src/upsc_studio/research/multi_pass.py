"""Multi-pass research and substantive fact-verification workflow."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from upsc_studio.db.schemas import utc_now_iso
from upsc_studio.research.verifier import EvidenceEngine, SOURCE_TIERS, HIGH_IMPACT_PATTERNS


class ClaimNature(str, Enum):
    FACT = "FACT"
    INTERPRETATION = "INTERPRETATION"
    DISPUTED_CLAIM = "DISPUTED_CLAIM"
    UNKNOWN = "UNKNOWN"
    PREDICTION = "PREDICTION"


class MultiPassStatus(str, Enum):
    VERIFIED = "VERIFIED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    OUTDATED = "OUTDATED"
    CONFLICTING = "CONFLICTING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass
class EvaluatedClaim:
    claim_id: str
    statement: str
    nature: ClaimNature
    source_id: Optional[str]
    source_title: str
    source_tier: str
    page_or_section: str
    evidence_excerpt: str
    status: MultiPassStatus
    is_safe_for_narration: bool
    rejection_reasons: list[str] = field(default_factory=list)
    reference_period: Optional[str] = None


@dataclass
class MultiPassResearchReport:
    topic_title: str
    cutoff_date: str
    total_claims_extracted: int
    verified_facts_count: int
    interpretations_count: int
    disputed_claims_count: int
    unknowns_count: int
    insufficient_evidence_count: int
    outdated_claims_count: int
    conflicting_claims_count: int
    safe_narration_claims: list[EvaluatedClaim] = field(default_factory=list)
    excluded_claims: list[EvaluatedClaim] = field(default_factory=list)
    sources_summary: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_title": self.topic_title,
            "cutoff_date": self.cutoff_date,
            "total_claims_extracted": self.total_claims_extracted,
            "verified_facts_count": self.verified_facts_count,
            "interpretations_count": self.interpretations_count,
            "disputed_claims_count": self.disputed_claims_count,
            "unknowns_count": self.unknowns_count,
            "insufficient_evidence_count": self.insufficient_evidence_count,
            "outdated_claims_count": self.outdated_claims_count,
            "conflicting_claims_count": self.conflicting_claims_count,
            "safe_narration_claims_count": len(self.safe_narration_claims),
            "excluded_claims_count": len(self.excluded_claims),
            "sources_count": len(self.sources_summary),
        }


class MultiPassResearchWorkflow:
    """Orchestrates 7-pass evidence review ensuring unsupported claims never enter narration as facts."""

    def __init__(self, conn: sqlite3.Connection, project_dir: Path) -> None:
        self.conn = conn
        self.project_dir = project_dir
        self.engine = EvidenceEngine(conn, project_dir)

    def run_multi_pass_audit(
        self,
        project_id: str,
        topic_title: str,
        cutoff_date: str,
        raw_text_corpus: str = "",
    ) -> MultiPassResearchReport:
        # Pass 1: Identify registered sources
        sources_rows = self.conn.execute("SELECT * FROM sources WHERE project_id = ?", (project_id,)).fetchall()
        sources_map = {s["id"]: dict(s) for s in sources_rows}

        # Pass 2: Claim extraction if raw notes supplied
        if raw_text_corpus.strip():
            self.engine.extract_claims_from_text(
                project_id=project_id,
                chapter_section="User Supplied Notes",
                text=raw_text_corpus,
                default_source_id=list(sources_map.keys())[0] if sources_map else None,
            )

        claims_rows = self.conn.execute("SELECT * FROM claims WHERE project_id = ?", (project_id,)).fetchall()

        cutoff_year = int(cutoff_date[:4]) if len(cutoff_date) >= 4 else 2026
        safe_claims: list[EvaluatedClaim] = []
        excluded_claims: list[EvaluatedClaim] = []

        verified_count = 0
        interpretations_count = 0
        disputed_count = 0
        unknowns_count = 0
        insufficient_count = 0
        outdated_count = 0
        conflicting_count = 0

        # Pass 3-7: Claim-level substantive analysis
        for c in claims_rows:
            stmt = c["statement"]
            s_id = c["source_id"]
            page_ref = c["page_or_section"] or ""
            ref_period = c["ref_period"]
            v_notes = c["verification_notes"] or ""

            # Classify Claim Nature
            low = stmt.lower()
            if any(k in low for k in ("may", "might", "could be argued", "viewed as", "theorized")):
                nature = ClaimNature.INTERPRETATION
                interpretations_count += 1
            elif any(k in low for k in ("will happen in", "expected to reach", "forecasted", "projected")):
                nature = ClaimNature.PREDICTION
                interpretations_count += 1
            elif any(k in low for k in ("disputed", "controversial", "conflicting data", "debated")):
                nature = ClaimNature.DISPUTED_CLAIM
                disputed_count += 1
            elif any(k in low for k in ("unknown", "unresolved", "not yet determined", "uncertain")):
                nature = ClaimNature.UNKNOWN
                unknowns_count += 1
            else:
                nature = ClaimNature.FACT

            reasons: list[str] = []
            status = MultiPassStatus.VERIFIED

            # Check 1: Missing Source or Empty Page Reference
            if not s_id or s_id not in sources_map:
                status = MultiPassStatus.INSUFFICIENT_EVIDENCE
                reasons.append("Lacks authoritative linked source in bibliography.")
                insufficient_count += 1
            elif not page_ref or len(page_ref.strip()) < 2:
                status = MultiPassStatus.INSUFFICIENT_EVIDENCE
                reasons.append("Lacks specific page, section, or paragraph pinpoint reference.")
                insufficient_count += 1

            # Check 2: Outdated Information against Cutoff Date
            src_info = sources_map.get(s_id, {})
            pub_date = src_info.get("pub_date", "")
            yr_match = re.search(r"\b(19\d{2}|20\d{2})\b", pub_date or stmt)
            if yr_match and int(yr_match.group(1)) > cutoff_year:
                status = MultiPassStatus.OUTDATED
                reasons.append(f"Source year {yr_match.group(1)} exceeds project research cutoff year {cutoff_year}.")
                outdated_count += 1

            # Check 3: Contradicting annotations
            if "conflict" in v_notes.lower() or c["status"] == "CONFLICTING":
                status = MultiPassStatus.CONFLICTING
                reasons.append("Contradicted by another registered source in evidence ledger.")
                conflicting_count += 1

            # Determine whether safe for documentary narration
            is_safe = (status == MultiPassStatus.VERIFIED and nature != ClaimNature.PREDICTION)
            if status == MultiPassStatus.VERIFIED and nature == ClaimNature.FACT:
                verified_count += 1

            eval_claim = EvaluatedClaim(
                claim_id=c["id"],
                statement=stmt,
                nature=nature,
                source_id=s_id,
                source_title=src_info.get("title", "Unknown Source"),
                source_tier=src_info.get("source_tier", "OTHER"),
                page_or_section=page_ref,
                evidence_excerpt=v_notes,
                status=status,
                is_safe_for_narration=is_safe,
                rejection_reasons=reasons,
                reference_period=ref_period,
            )

            # Persist status to SQLite
            db_status = "VERIFIED" if is_safe else "UNSUPPORTED"
            notes_str = f"[{status.value}] " + ("; ".join(reasons) if reasons else v_notes)
            self.conn.execute(
                "UPDATE claims SET status = ?, verification_notes = ? WHERE id = ?",
                (db_status, notes_str, c["id"]),
            )

            if is_safe:
                safe_claims.append(eval_claim)
            else:
                excluded_claims.append(eval_claim)

        self.conn.commit()

        # Build report
        report = MultiPassResearchReport(
            topic_title=topic_title,
            cutoff_date=cutoff_date,
            total_claims_extracted=len(claims_rows),
            verified_facts_count=verified_count,
            interpretations_count=interpretations_count,
            disputed_claims_count=disputed_count,
            unknowns_count=unknowns_count,
            insufficient_evidence_count=insufficient_count,
            outdated_claims_count=outdated_count,
            conflicting_claims_count=conflicting_count,
            safe_narration_claims=safe_claims,
            excluded_claims=excluded_claims,
            sources_summary=[dict(s) for s in sources_rows],
        )

        out_path = self.project_dir / "research" / "multi_pass_research_report.json"
        out_path.write_text(
            json.dumps(
                {
                    "summary": report.to_dict(),
                    "safe_claims": [asdict(c) for c in safe_claims],
                    "excluded_claims": [asdict(c) for c in excluded_claims],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        return report
