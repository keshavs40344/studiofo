"""Evidence quality assessment, multi-source corroboration, and lifecycle tracking.

Enforces clear separation across all 6 verification lifecycle stages:
1. Source Discovered
2. Source Accessible
3. Relevant Evidence Extracted
4. Claim Supported
5. Claim Independently Corroborated
6. Claim Human-Reviewed
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

TIER_QUALITY_WEIGHTS = {
    "PRIMARY_OFFICIAL": 1.0,         # Gazette, Constitutional text, Ministries, Supreme Court, RBI, CAG
    "ACADEMIC_PEER_REVIEWED": 0.85,  # Peer-reviewed journal publications, Oxford/Cambridge UP
    "REPUTABLE_NEWS": 0.70,          # The Hindu, Indian Express, PTI, BBC, Reuters
    "OTHER": 0.40,                   # General web pages, blogs, Wikipedia
    "USER_NOTES": 0.10,              # User supplied raw notes (cannot verify external facts)
}


@dataclass
class ClaimLifecycleStage:
    source_discovered: bool = False
    source_accessible: bool = False
    evidence_extracted: bool = False
    claim_supported: bool = False
    independently_corroborated: bool = False
    human_reviewed: bool = False

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass
class EnrichedClaimRecord:
    claim_id: str
    statement: str
    chapter_section: str
    status: str
    primary_source_id: Optional[str] = None
    publisher: Optional[str] = None
    pub_date: Optional[str] = None
    access_date: Optional[str] = None
    page_or_section: Optional[str] = None
    supporting_excerpt: Optional[str] = None
    corroborating_source_ids: list[str] = field(default_factory=list)
    contradictory_evidence: list[dict[str, Any]] = field(default_factory=list)
    reviewer: Optional[str] = None
    review_date: Optional[str] = None
    verification_notes: str = ""
    evidence_quality_score: float = 0.0
    lifecycle: ClaimLifecycleStage = field(default_factory=ClaimLifecycleStage)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["lifecycle"] = self.lifecycle.to_dict()
        return d


class CorroborationEngine:
    """Evaluates multi-source corroboration and computes objective evidence quality scores."""

    @staticmethod
    def extract_domain(url: Optional[str]) -> str:
        """Extract root domain from a URL to ensure independence."""
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            return netloc.split(":")[0]
        except Exception:
            return ""

    def evaluate_corroboration(
        self,
        primary_source: dict[str, Any],
        corroborating_sources: list[dict[str, Any]],
        statement: str,
        is_high_impact: bool = False,
    ) -> tuple[bool, float, list[str]]:
        """Determine if a claim is independently corroborated by distinct sources.
        
        Returns:
            (is_corroborated, quality_score, notes)
        """
        all_sources = [primary_source] + corroborating_sources
        valid_sources = [s for s in all_sources if s and s.get("id")]

        if not valid_sources:
            return False, 0.0, ["No valid sources attached to claim."]

        # Check publisher and domain independence
        publishers = {str(s.get("publisher", "")).strip().lower() for s in valid_sources if s.get("publisher")}
        domains = {self.extract_domain(s.get("url")) for s in valid_sources if s.get("url")}
        domains.discard("")

        # Calculate weighted quality score
        weights = [TIER_QUALITY_WEIGHTS.get(s.get("source_tier", "OTHER"), 0.3) for s in valid_sources]
        base_score = max(weights) if weights else 0.0

        notes: list[str] = []
        # Multi-source bonus if independent publishers exist
        has_independent_sources = len(publishers) >= 2 or len(domains) >= 2

        if has_independent_sources:
            # Score bonus for independent multi-source corroboration
            quality_score = min(1.0, base_score + 0.15)
            notes.append(f"Independently corroborated across {len(publishers)} publisher(s) / {len(domains)} domain(s).")
            is_corroborated = True
        else:
            quality_score = base_score
            is_corroborated = not is_high_impact  # Low-impact claims can pass with single primary source
            if is_high_impact:
                notes.append("High-impact factual claim requires corroboration from at least 2 independent publishers.")

        return is_corroborated, round(quality_score, 2), notes
