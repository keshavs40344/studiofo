"""Research, evidence verification, and source integrity package."""

from upsc_studio.research.contradictions import ContradictionDetector, ContradictionRecord
from upsc_studio.research.corroborator import CorroborationEngine, TIER_QUALITY_WEIGHTS
from upsc_studio.research.discovery import ResearchDiscovery
from upsc_studio.research.extractor import DocumentExtractor, DocumentSection, AtomicClaimCandidate
from upsc_studio.research.planner import ResearchDimension, ResearchPlan, ResearchPlanner, ResearchPriority
from upsc_studio.research.security import ResearchSecurityError, ResearchSecurityGuard
from upsc_studio.research.verifier import EvidenceEngine, SOURCE_TIERS

__all__ = [
    "AtomicClaimCandidate",
    "ContradictionDetector",
    "ContradictionRecord",
    "CorroborationEngine",
    "DocumentExtractor",
    "DocumentSection",
    "EvidenceEngine",
    "ResearchDimension",
    "ResearchDiscovery",
    "ResearchPlan",
    "ResearchPlanner",
    "ResearchPriority",
    "ResearchSecurityError",
    "ResearchSecurityGuard",
    "SOURCE_TIERS",
    "TIER_QUALITY_WEIGHTS",
]
