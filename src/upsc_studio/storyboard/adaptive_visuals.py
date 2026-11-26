"""Adaptive visual intelligence: selects visual category from subject domain and teaching objective."""

from __future__ import annotations

SPECIALIST_VISUAL_MAP = {
    "GS-I": {
        "intro": "Historical Timeline / Archival Card",
        "mechanism": "Historical & Physical Map",
        "analysis": "Before/After Continuity Table",
    },
    "GS-II": {
        "intro": "Constitutional Context Card",
        "mechanism": "Animated Constitutional Process",
        "analysis": "Institutional & Jurisdictional Map",
    },
    "GS-III": {
        "intro": "Macro/Sectoral Indicator Card",
        "mechanism": "Economic / Ecosystem Mechanism Flowchart",
        "analysis": "Source-Cited Data Comparison Chart",
    },
    "GS-IV": {
        "intro": "Ethical Principle & Definition Card",
        "mechanism": "Stakeholder & Dilemma Decision Tree",
        "analysis": "Case-Study Resolution Matrix",
    },
    "PRELIMS_CSAT": {
        "intro": "Problem Statement & Units Card",
        "mechanism": "Step-by-Step Problem-Solving Animation",
        "analysis": "Annotated Data Table & Trap Check",
    },
}


class AdaptiveVisualSelector:
    """Selects purposeful educational visuals tailored to subject specialist and section role."""

    @staticmethod
    def choose_visual(specialist_key: str, section_role: str, chapter_title: str) -> str:
        title_l = chapter_title.lower()
        if "monsoon" in title_l or "geography" in title_l or "biodiversity" in title_l:
            if section_role == "mechanism":
                return "Map / Ecosystem Process Diagram"
        domain = SPECIALIST_VISUAL_MAP.get(specialist_key, SPECIALIST_VISUAL_MAP["GS-II"])
        return domain.get(section_role, "Clean Teaching Slide")
