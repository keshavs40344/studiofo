"""Current Affairs Research Engine: Live source verification, multi-tier evidence priority, and fact vs prediction classification."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SourcePriorityTier(str, Enum):
    TIER_1_OFFICIAL_GOVT = "PRIMARY_OFFICIAL_GOVT"           # PIB, Gazette of India, Ministry releases
    TIER_2_PARLIAMENT_LEGISLATION = "PRIMARY_LEGISLATION"      # Acts, Bills, Committee Reports
    TIER_3_JUDICIAL_VERDICT = "JUDICIAL_VERDICT"               # Supreme Court / High Court signed judgments
    TIER_4_STATUTORY_REGULATOR = "STATUTORY_REGULATOR"         # RBI, SEBI, ECI, CAG reports
    TIER_5_INTERNATIONAL_ORG = "INTERNATIONAL_ORG"            # UN, WHO, IMF, World Bank, WTO
    TIER_6_PEER_REVIEWED = "PEER_REVIEWED_RESEARCH"           # Nature, Science, Lancet, peer-reviewed journals
    TIER_7_REPUTABLE_NEWS = "REPUTABLE_NEWS"                  # Established news with multi-source reporting
    TIER_8_SECONDARY_ANALYSIS = "SECONDARY_ANALYSIS"          # Think-tank reports, editorial commentaries


class ClaimNature(str, Enum):
    CONFIRMED_FACT = "CONFIRMED_FACT"
    OFFICIAL_STATEMENT = "OFFICIAL_STATEMENT"
    MEDIA_REPORT = "MEDIA_REPORT"
    EXPERT_INTERPRETATION = "EXPERT_INTERPRETATION"
    ALLEGATION = "ALLEGATION"
    OPINION = "OPINION"
    PREDICTION = "PREDICTION"
    UNRESOLVED_INFORMATION = "UNRESOLVED_INFORMATION"


@dataclass
class CurrentAffairsClaim:
    claim_id: str
    claim_text: str
    claim_nature: ClaimNature
    source_title: str
    source_tier: SourcePriorityTier
    source_url: str
    event_date: str
    publication_date: str
    research_date: str
    primary_source_available: bool
    verified: bool
    known_uncertainties: list[str] = field(default_factory=list)
    information_cutoff_date: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["claim_nature"] = self.claim_nature.value
        d["source_tier"] = self.source_tier.value
        return d


@dataclass
class CurrentAffairsResearchReport:
    topic_title: str
    research_date: str
    information_cutoff_date: str
    total_claims_assessed: int
    confirmed_facts_count: int
    official_statements_count: int
    predictions_labelled_count: int
    unresolved_uncertainties_count: int
    claims: list[CurrentAffairsClaim]
    update_alerts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_title": self.topic_title,
            "research_date": self.research_date,
            "information_cutoff_date": self.information_cutoff_date,
            "total_claims_assessed": self.total_claims_assessed,
            "confirmed_facts_count": self.confirmed_facts_count,
            "official_statements_count": self.official_statements_count,
            "predictions_labelled_count": self.predictions_labelled_count,
            "unresolved_uncertainties_count": self.unresolved_uncertainties_count,
            "claims": [c.to_dict() for c in self.claims],
            "update_alerts": self.update_alerts,
        }


class CurrentAffairsResearchEngine:
    """Verifies fast-moving developments using strict primary evidence tiers and transparent cutoff dates."""

    def __init__(self, cutoff_date: Optional[str] = None) -> None:
        self.cutoff_date = cutoff_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def register_claim(
        self,
        claim_id: str,
        text: str,
        nature: ClaimNature,
        source_title: str,
        source_tier: SourcePriorityTier,
        source_url: str,
        event_date: str,
        publication_date: str,
        primary_source_available: bool = True,
        known_uncertainties: Optional[list[str]] = None,
    ) -> CurrentAffairsClaim:
        """Add and validate a current-affairs claim enforcing strict labeling rules."""
        # RULE: Never present a prediction as a confirmed fact
        if nature == ClaimNature.PREDICTION and any(
            w in text.lower() for w in ["will definitely", "proven", "established fact", "has occurred"]
        ):
            raise ValueError(f"Integrity violation in '{claim_id}': Future prediction cannot be framed as established fact.")

        now = utc_now_iso()
        uncertainties = known_uncertainties or []

        # Validate tier & verification
        is_verified = (
            primary_source_available
            and source_tier in {
                SourcePriorityTier.TIER_1_OFFICIAL_GOVT,
                SourcePriorityTier.TIER_2_PARLIAMENT_LEGISLATION,
                SourcePriorityTier.TIER_3_JUDICIAL_VERDICT,
                SourcePriorityTier.TIER_4_STATUTORY_REGULATOR,
                SourcePriorityTier.TIER_5_INTERNATIONAL_ORG,
                SourcePriorityTier.TIER_6_PEER_REVIEWED,
            }
            and not uncertainties
        )

        return CurrentAffairsClaim(
            claim_id=claim_id,
            claim_text=text,
            claim_nature=nature,
            source_title=source_title,
            source_tier=source_tier,
            source_url=source_url,
            event_date=event_date,
            publication_date=publication_date,
            research_date=now[:10],
            primary_source_available=primary_source_available,
            verified=is_verified,
            known_uncertainties=uncertainties,
            information_cutoff_date=self.cutoff_date,
        )

    def evaluate_live_research(
        self,
        topic_title: str,
        claims: list[CurrentAffairsClaim],
        existing_doc_date: Optional[str] = None,
    ) -> CurrentAffairsResearchReport:
        """Audit current affairs claims package and detect needed updates for existing videos."""
        confirmed_count = sum(1 for c in claims if c.claim_nature == ClaimNature.CONFIRMED_FACT)
        statements_count = sum(1 for c in claims if c.claim_nature == ClaimNature.OFFICIAL_STATEMENT)
        predictions_count = sum(1 for c in claims if c.claim_nature == ClaimNature.PREDICTION)
        uncertainties_count = sum(1 for c in claims if c.known_uncertainties)

        alerts: list[str] = []
        if existing_doc_date:
            newer_events = [c for c in claims if c.event_date > existing_doc_date]
            if newer_events:
                alerts.append(
                    f"Update required: {len(newer_events)} event(s) occurred after existing documentary publication date ({existing_doc_date})."
                )

        return CurrentAffairsResearchReport(
            topic_title=topic_title,
            research_date=utc_now_iso()[:10],
            information_cutoff_date=self.cutoff_date,
            total_claims_assessed=len(claims),
            confirmed_facts_count=confirmed_count,
            official_statements_count=statements_count,
            predictions_labelled_count=predictions_count,
            unresolved_uncertainties_count=uncertainties_count,
            claims=claims,
            update_alerts=alerts,
        )
