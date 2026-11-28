"""Visual Direction Engine: maps educational concepts to optimal documentary visual forms."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from upsc_studio.graphics.design_system import LayoutOrientation


class VisualType(str, Enum):
    HISTORICAL_TIMELINE = "HISTORICAL_TIMELINE"
    GEOGRAPHICAL_MAP = "GEOGRAPHICAL_MAP"
    INSTITUTIONAL_DIAGRAM = "INSTITUTIONAL_DIAGRAM"
    PROCESS_ANIMATION = "PROCESS_ANIMATION"
    SCIENTIFIC_ILLUSTRATION = "SCIENTIFIC_ILLUSTRATION"
    DATA_VISUALISATION = "DATA_VISUALISATION"
    STATISTICAL_COMPARISON = "STATISTICAL_COMPARISON"
    ARCHITECTURAL_DIAGRAM = "ARCHITECTURAL_DIAGRAM"
    FLOWCHART = "FLOWCHART"
    SPLIT_COMPARISON = "SPLIT_COMPARISON"
    ANIMATED_LABELS = "ANIMATED_LABELS"
    ANNOTATED_ILLUSTRATION = "ANNOTATED_ILLUSTRATION"
    STEP_MECHANISM = "STEP_MECHANISM"
    CONCEPT_CARD = "CONCEPT_CARD"


@dataclass
class VisualDirectionDecision:
    scene_id: str
    section_id: str
    section_title: str
    visual_type: VisualType
    rationale: str
    recommended_animation: str
    required_evidence_type: str
    layout: LayoutOrientation = LayoutOrientation.LANDSCAPE_16_9

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["visual_type"] = self.visual_type.value
        d["layout"] = self.layout.value
        return d


class VisualDirectionEngine:
    """Selects purposeful, pedagogically justified visual representations for educational documentary scenes."""

    KEYWORDS = {
        VisualType.HISTORICAL_TIMELINE: (
            r"\b(?:timeline|evolution|chronolog|history|historical|epoch|century|ancient|medieval|milestone|19\d{2}|18\d{2})\b"
        ),
        VisualType.GEOGRAPHICAL_MAP: (
            r"\b(?:map|geograph|terrain|spatial|river|basin|monsoon|corridor|peninsula|boundary|plateau|state|district|himalaya|coastal)\b"
        ),
        VisualType.INSTITUTIONAL_DIAGRAM: (
            r"\b(?:institution|commission|ministry|court|judiciary|parliament|tribunal|jurisdiction|separation\s+of\s+powers|authority|organ)\b"
        ),
        VisualType.DATA_VISUALISATION: (
            r"\b(?:data|statistic|chart|percent|%|gdp|growth|rate|inflation|share|census|expenditure|budget|indicator|survey)\b"
        ),
        VisualType.SPLIT_COMPARISON: (
            r"\b(?:compare|comparison|versus|vs|before\s+and\s+after|challenges\s+and\s+reforms|strengths|arguments|counterarguments|pros\s+and\s+cons)\b"
        ),
        VisualType.FLOWCHART: (
            r"\b(?:flowchart|decision|criteria|test|pathway|branch|algorithm|conditions|eligibility|disqualification)\b"
        ),
        VisualType.SCIENTIFIC_ILLUSTRATION: (
            r"\b(?:photosynthesis|chlorophyll|cellular|organism|ecosystem|trophic|physics|chemical|reaction|wave|orbit|spectrum)\b"
        ),
        VisualType.PROCESS_ANIMATION: (
            r"\b(?:mechanism|process|procedure|step[\s-]by[\s-]step|amendment\s+procedure|legislative\s+passage|cycle|workflow)\b"
        ),
    }

    def determine_visual(
        self,
        scene_id: str,
        section_id: str,
        title: str,
        objective: str,
        narration: str,
        content_category: str = "upsc",
        visual_category: str = "",
        layout: LayoutOrientation = LayoutOrientation.LANDSCAPE_16_9,
    ) -> VisualDirectionDecision:
        """Analyze conceptual context and assign the optimal explanatory visual type."""
        # Direct category mapping if explicitly declared in visual_category
        cat_l = visual_category.lower().strip()
        if "timeline" in cat_l:
            return VisualDirectionDecision(
                scene_id=scene_id, section_id=section_id, section_title=title,
                visual_type=VisualType.HISTORICAL_TIMELINE,
                rationale="Historical timeline explicitly indicated in visual specifications.",
                recommended_animation="timeline_progression",
                required_evidence_type="Gazette / Official Historical Record", layout=layout,
            )
        if "process" in cat_l or "mechanism" in cat_l:
            return VisualDirectionDecision(
                scene_id=scene_id, section_id=section_id, section_title=title,
                visual_type=VisualType.PROCESS_ANIMATION,
                rationale="Step-by-step process animation explicitly indicated in visual specifications.",
                recommended_animation="step_process_reveal",
                required_evidence_type="Procedural rules / Standard operating procedure", layout=layout,
            )
        if "map" in cat_l:
            return VisualDirectionDecision(
                scene_id=scene_id, section_id=section_id, section_title=title,
                visual_type=VisualType.GEOGRAPHICAL_MAP,
                rationale="Thematic or jurisdictional map explicitly indicated in visual specifications.",
                recommended_animation="map_callout_highlight",
                required_evidence_type="Survey of India / Administrative Boundary", layout=layout,
            )

        text = f"{title} {objective} {narration}".lower()

        # Check in priority order of specific pedagogical requirements
        if re.search(self.KEYWORDS[VisualType.SPLIT_COMPARISON], text):
            return VisualDirectionDecision(
                scene_id=scene_id,
                section_id=section_id,
                section_title=title,
                visual_type=VisualType.SPLIT_COMPARISON,
                rationale="Analytical section requiring comparative before/after or reform-challenge evaluation.",
                recommended_animation="split_screen_reveal",
                required_evidence_type="Comparative source data / case law",
                layout=layout,
            )

        if re.search(self.KEYWORDS[VisualType.DATA_VISUALISATION], text):
            return VisualDirectionDecision(
                scene_id=scene_id,
                section_id=section_id,
                section_title=title,
                visual_type=VisualType.DATA_VISUALISATION,
                rationale="Quantitative claims require a verified, source-cited data chart with clear units.",
                recommended_animation="progressive_bar_reveal",
                required_evidence_type="MoSPI / Census / Official Budget Statistics",
                layout=layout,
            )

        if re.search(self.KEYWORDS[VisualType.GEOGRAPHICAL_MAP], text):
            return VisualDirectionDecision(
                scene_id=scene_id,
                section_id=section_id,
                section_title=title,
                visual_type=VisualType.GEOGRAPHICAL_MAP,
                rationale="Spatial relationships and territorial scope require an authenticated thematic map.",
                recommended_animation="map_callout_highlight",
                required_evidence_type="Survey of India / Official Administrative Boundary",
                layout=layout,
            )

        if re.search(self.KEYWORDS[VisualType.HISTORICAL_TIMELINE], text):
            return VisualDirectionDecision(
                scene_id=scene_id,
                section_id=section_id,
                section_title=title,
                visual_type=VisualType.HISTORICAL_TIMELINE,
                rationale="Chronological progression requires a step-by-step milestone timeline.",
                recommended_animation="timeline_progression",
                required_evidence_type="Gazette / Official Historical Record",
                layout=layout,
            )

        if re.search(self.KEYWORDS[VisualType.FLOWCHART], text):
            return VisualDirectionDecision(
                scene_id=scene_id,
                section_id=section_id,
                section_title=title,
                visual_type=VisualType.FLOWCHART,
                rationale="Procedural decision criteria require an unambiguous logical decision tree.",
                recommended_animation="flow_branch_trace",
                required_evidence_type="Statutory procedural framework",
                layout=layout,
            )

        if re.search(self.KEYWORDS[VisualType.SCIENTIFIC_ILLUSTRATION], text):
            return VisualDirectionDecision(
                scene_id=scene_id,
                section_id=section_id,
                section_title=title,
                visual_type=VisualType.SCIENTIFIC_ILLUSTRATION,
                rationale="Scientific transformation requires a schematic diagram of the mechanism.",
                recommended_animation="cycle_demonstration",
                required_evidence_type="NCERT / Peer-reviewed scientific schema",
                layout=layout,
            )

        if re.search(self.KEYWORDS[VisualType.INSTITUTIONAL_DIAGRAM], text):
            return VisualDirectionDecision(
                scene_id=scene_id,
                section_id=section_id,
                section_title=title,
                visual_type=VisualType.INSTITUTIONAL_DIAGRAM,
                rationale="Constitutional or institutional relationships require a jurisdictional structure diagram.",
                recommended_animation="node_relationship_reveal",
                required_evidence_type="Constitution of India / Statutory Mandate",
                layout=layout,
            )

        if re.search(self.KEYWORDS[VisualType.PROCESS_ANIMATION], text):
            return VisualDirectionDecision(
                scene_id=scene_id,
                section_id=section_id,
                section_title=title,
                visual_type=VisualType.PROCESS_ANIMATION,
                rationale="Multi-step mechanism requires a progressive operational animation.",
                recommended_animation="step_process_reveal",
                required_evidence_type="Procedural rules / Standard operating procedure",
                layout=layout,
            )

        # Default pedagogical card
        return VisualDirectionDecision(
            scene_id=scene_id,
            section_id=section_id,
            section_title=title,
            visual_type=VisualType.CONCEPT_CARD,
            rationale="Foundational concept presentation with structured definitions and key takeaways.",
            recommended_animation="fade_in_keypoints",
            required_evidence_type="Verified syllabus definition",
            layout=layout,
        )
