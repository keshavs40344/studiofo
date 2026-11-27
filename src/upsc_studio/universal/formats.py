"""Documentary Formats: 10 configurable production formats with duration planning and series recommendations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Optional


class DocumentaryFormatType(str, Enum):
    COMPLETE_CHAPTER_DOCUMENTARY = "COMPLETE_CHAPTER_DOCUMENTARY"
    DEEP_DIVE_EXPLAINER = "DEEP_DIVE_EXPLAINER"
    CURRENT_AFFAIRS_ANALYSIS = "CURRENT_AFFAIRS_ANALYSIS"
    HISTORICAL_DOCUMENTARY = "HISTORICAL_DOCUMENTARY"
    SCIENCE_TECH_EXPLAINER = "SCIENCE_TECH_EXPLAINER"
    CONCEPT_BY_CONCEPT_LESSON = "CONCEPT_BY_CONCEPT_LESSON"
    CASE_STUDY_DOCUMENTARY = "CASE_STUDY_DOCUMENTARY"
    SHORT_DOCUMENTARY = "SHORT_DOCUMENTARY"
    DOCUMENTARY_SERIES = "DOCUMENTARY_SERIES"
    REVISION_RECAP_EPISODE = "REVISION_RECAP_EPISODE"


@dataclass
class FormatSpecification:
    format_type: DocumentaryFormatType
    name: str
    description: str
    min_duration_min: int
    max_duration_min: int
    recommended_duration_min: int
    recommended_wpm: float
    target_scene_duration_sec: float
    max_subtopics_per_video: int
    supports_series_split: bool
    disclaimer: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["format_type"] = self.format_type.value
        return d


FORMAT_REGISTRY: dict[DocumentaryFormatType, FormatSpecification] = {
    DocumentaryFormatType.COMPLETE_CHAPTER_DOCUMENTARY: FormatSpecification(
        format_type=DocumentaryFormatType.COMPLETE_CHAPTER_DOCUMENTARY,
        name="Complete Chapter Documentary",
        description="Comprehensive syllabus and domain chapter covering foundational definitions, mechanisms, landmark precedents, and analytical evaluation.",
        min_duration_min=15,
        max_duration_min=45,
        recommended_duration_min=25,
        recommended_wpm=130.0,
        target_scene_duration_sec=75.0,
        max_subtopics_per_video=14,
        supports_series_split=True,
    ),
    DocumentaryFormatType.DEEP_DIVE_EXPLAINER: FormatSpecification(
        format_type=DocumentaryFormatType.DEEP_DIVE_EXPLAINER,
        name="Deep-Dive Explainer",
        description="In-depth, single-subject investigative documentary detailing origins, structural principles, and modern frontiers.",
        min_duration_min=12,
        max_duration_min=30,
        recommended_duration_min=18,
        recommended_wpm=128.0,
        target_scene_duration_sec=70.0,
        max_subtopics_per_video=8,
        supports_series_split=True,
    ),
    DocumentaryFormatType.CURRENT_AFFAIRS_ANALYSIS: FormatSpecification(
        format_type=DocumentaryFormatType.CURRENT_AFFAIRS_ANALYSIS,
        name="Current Affairs Analysis",
        description="Fast-moving policy, judgment, international, or scientific event deconstruction with explicit verification dates and official source tiers.",
        min_duration_min=8,
        max_duration_min=20,
        recommended_duration_min=12,
        recommended_wpm=135.0,
        target_scene_duration_sec=60.0,
        max_subtopics_per_video=6,
        supports_series_split=False,
    ),
    DocumentaryFormatType.HISTORICAL_DOCUMENTARY: FormatSpecification(
        format_type=DocumentaryFormatType.HISTORICAL_DOCUMENTARY,
        name="Historical Documentary",
        description="Chronological, narrative-driven documentary with animated timelines, territorial maps, and archival analysis.",
        min_duration_min=15,
        max_duration_min=40,
        recommended_duration_min=22,
        recommended_wpm=125.0,
        target_scene_duration_sec=80.0,
        max_subtopics_per_video=10,
        supports_series_split=True,
    ),
    DocumentaryFormatType.SCIENCE_TECH_EXPLAINER: FormatSpecification(
        format_type=DocumentaryFormatType.SCIENCE_TECH_EXPLAINER,
        name="Science & Technology Explainer",
        description="Step-by-step physical, biological, cellular, or computational mechanism visualization with diagrams and simulations.",
        min_duration_min=10,
        max_duration_min=25,
        recommended_duration_min=15,
        recommended_wpm=126.0,
        target_scene_duration_sec=65.0,
        max_subtopics_per_video=6,
        supports_series_split=True,
    ),
    DocumentaryFormatType.CONCEPT_BY_CONCEPT_LESSON: FormatSpecification(
        format_type=DocumentaryFormatType.CONCEPT_BY_CONCEPT_LESSON,
        name="Concept-by-Concept Lesson",
        description="Targeted single-concept teaching session designed for modular syllabus playlists and prerequisite building.",
        min_duration_min=6,
        max_duration_min=15,
        recommended_duration_min=10,
        recommended_wpm=130.0,
        target_scene_duration_sec=55.0,
        max_subtopics_per_video=3,
        supports_series_split=False,
    ),
    DocumentaryFormatType.CASE_STUDY_DOCUMENTARY: FormatSpecification(
        format_type=DocumentaryFormatType.CASE_STUDY_DOCUMENTARY,
        name="Case-Study Documentary",
        description="Detailed examination of a real-world legal judgment, historical event, environmental incident, or economic crisis.",
        min_duration_min=10,
        max_duration_min=25,
        recommended_duration_min=16,
        recommended_wpm=132.0,
        target_scene_duration_sec=65.0,
        max_subtopics_per_video=5,
        supports_series_split=True,
    ),
    DocumentaryFormatType.SHORT_DOCUMENTARY: FormatSpecification(
        format_type=DocumentaryFormatType.SHORT_DOCUMENTARY,
        name="Short Documentary (Single Concept Focus)",
        description="Concise 5-8 minute spotlight on a specific provision, rule, or question. Does NOT substitute for full topic coverage.",
        min_duration_min=4,
        max_duration_min=8,
        recommended_duration_min=6,
        recommended_wpm=138.0,
        target_scene_duration_sec=45.0,
        max_subtopics_per_video=2,
        supports_series_split=False,
        disclaimer="Short documentary format covers a focused single aspect only and must not be labelled as complete topic coverage.",
    ),
    DocumentaryFormatType.DOCUMENTARY_SERIES: FormatSpecification(
        format_type=DocumentaryFormatType.DOCUMENTARY_SERIES,
        name="Documentary Series (Multi-Part Episode Plan)",
        description="Multi-episode series plan dividing large, interconnected subjects into sequenced comprehensive videos.",
        min_duration_min=30,
        max_duration_min=180,
        recommended_duration_min=60,
        recommended_wpm=130.0,
        target_scene_duration_sec=70.0,
        max_subtopics_per_video=25,
        supports_series_split=True,
    ),
    DocumentaryFormatType.REVISION_RECAP_EPISODE: FormatSpecification(
        format_type=DocumentaryFormatType.REVISION_RECAP_EPISODE,
        name="Revision & Rapid Recap Episode",
        description="High-density exam revision session synthesizing essential factual anchors, mind maps, and common traps.",
        min_duration_min=8,
        max_duration_min=18,
        recommended_duration_min=12,
        recommended_wpm=140.0,
        target_scene_duration_sec=50.0,
        max_subtopics_per_video=12,
        supports_series_split=False,
    ),
}


class FormatSelector:
    """Selects and validates documentary format based on topic depth and target duration."""

    @staticmethod
    def get_format(format_type: DocumentaryFormatType) -> FormatSpecification:
        return FORMAT_REGISTRY[format_type]

    @staticmethod
    def recommend_format(
        subtopic_count: int,
        target_duration_min: int,
        is_current_affairs: bool = False,
    ) -> FormatSpecification:
        if is_current_affairs:
            return FORMAT_REGISTRY[DocumentaryFormatType.CURRENT_AFFAIRS_ANALYSIS]

        if subtopic_count >= 12:
            if target_duration_min > 30:
                return FORMAT_REGISTRY[DocumentaryFormatType.DOCUMENTARY_SERIES]
            return FORMAT_REGISTRY[DocumentaryFormatType.COMPLETE_CHAPTER_DOCUMENTARY]

        if subtopic_count <= 2 and target_duration_min <= 8:
            return FORMAT_REGISTRY[DocumentaryFormatType.SHORT_DOCUMENTARY]

        if target_duration_min <= 15:
            return FORMAT_REGISTRY[DocumentaryFormatType.CONCEPT_BY_CONCEPT_LESSON]

        return FORMAT_REGISTRY[DocumentaryFormatType.DEEP_DIVE_EXPLAINER]

    @staticmethod
    def validate_duration_for_topic(
        subtopic_count: int,
        target_duration_min: int,
    ) -> tuple[bool, Optional[str]]:
        """Ensure complex topics are not artificially compressed into inadequate short videos."""
        if subtopic_count >= 10 and target_duration_min < 12:
            return (
                False,
                f"Topic contains {subtopic_count} required subtopics which cannot be properly explained in {target_duration_min} minutes. "
                f"Minimum recommended duration is 15 minutes, or split into a connected Documentary Series.",
            )
        return True, None
