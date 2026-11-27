"""Specialist agent factory mapping roles and agent IDs to concrete agent instances."""

from __future__ import annotations

from typing import Optional
from upsc_studio.agents.contracts import AgentRole
from upsc_studio.agents.specialists.base import BaseSpecialistAgent
from upsc_studio.agents.specialists.research_agents import (
    ExecutiveProducerAgent,
    TopicResearcherAgent,
    ResearchSourceCollectorAgent,
    IndependentFactCheckerAgent,
    ClaimToSourceVerifierAgent,
    SourceFreshnessAuditorAgent,
)
from upsc_studio.agents.specialists.pedagogy_agents import (
    CurriculumMapperAgent,
    TopicCoverageAuditorAgent,
    InstructionalDesignerAgent,
    TeachingScriptWriterAgent,
    HinglishLanguageEditorAgent,
    DocumentaryStoryEditorAgent,
)
from upsc_studio.agents.specialists.visual_agents import (
    VisualResearchDirectorAgent,
    StoryboardArchitectAgent,
    AnimationPlannerAgent,
    DiagramInfographicPlannerAgent,
    AssetRightsAuditorAgent,
)
from upsc_studio.agents.specialists.audio_video_agents import (
    NarrationDirectorAgent,
    PronunciationAuditorAgent,
    AudioQualityAuditorAgent,
    SubtitleTranslationAgent,
    VideoQualityAuditorAgent,
)
from upsc_studio.agents.specialists.quality_release_agents import (
    AcademicRedTeamReviewerAgent,
    FinalReleaseGatekeeperAgent,
)

SPECIALIST_CLASSES: list[type[BaseSpecialistAgent]] = [
    ExecutiveProducerAgent,
    TopicResearcherAgent,
    ResearchSourceCollectorAgent,
    IndependentFactCheckerAgent,
    ClaimToSourceVerifierAgent,
    SourceFreshnessAuditorAgent,
    CurriculumMapperAgent,
    TopicCoverageAuditorAgent,
    InstructionalDesignerAgent,
    TeachingScriptWriterAgent,
    HinglishLanguageEditorAgent,
    DocumentaryStoryEditorAgent,
    VisualResearchDirectorAgent,
    StoryboardArchitectAgent,
    AnimationPlannerAgent,
    DiagramInfographicPlannerAgent,
    AssetRightsAuditorAgent,
    NarrationDirectorAgent,
    PronunciationAuditorAgent,
    AudioQualityAuditorAgent,
    SubtitleTranslationAgent,
    VideoQualityAuditorAgent,
    AcademicRedTeamReviewerAgent,
    FinalReleaseGatekeeperAgent,
]

_AGENT_ID_MAP: dict[str, type[BaseSpecialistAgent]] = {cls.agent_id: cls for cls in SPECIALIST_CLASSES}
_AGENT_ROLE_MAP: dict[AgentRole, type[BaseSpecialistAgent]] = {cls.role: cls for cls in SPECIALIST_CLASSES}


def get_specialist_agent(identifier: str | AgentRole) -> Optional[BaseSpecialistAgent]:
    """Retrieve an instantiated specialist agent by ID (e.g. 'AGENT_01') or role."""
    if isinstance(identifier, AgentRole):
        cls = _AGENT_ROLE_MAP.get(identifier)
    elif identifier in _AGENT_ID_MAP:
        cls = _AGENT_ID_MAP.get(identifier)
    else:
        try:
            role = AgentRole(identifier)
            cls = _AGENT_ROLE_MAP.get(role)
        except ValueError:
            cls = None
    return cls() if cls else None


def list_all_specialists() -> list[BaseSpecialistAgent]:
    """Return instances of all 24 specialist agents."""
    return [cls() for cls in SPECIALIST_CLASSES]
