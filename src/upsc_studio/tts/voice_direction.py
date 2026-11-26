"""Documentary Voice Direction Engine: Delivery Styles, Pacing, and Sentence Purpose Mapping."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel


class DeliveryStyle(str, Enum):
    DOCUMENTARY_NARRATOR = "DOCUMENTARY_NARRATOR"  # Clear, confident, balanced pacing
    CLASSROOM_TEACHER = "CLASSROOM_TEACHER"        # Engaging, pedagogic, clear cadence
    SERIOUS_CONSTITUTIONAL = "SERIOUS_CONSTITUTIONAL"  # Deliberate, formal, authoritative
    HISTORICAL_STORYTELLING = "HISTORICAL_STORYTELLING"  # Narrative, immersive, reflective
    ANALYTICAL_EXPLANATION = "ANALYTICAL_EXPLANATION"    # Methodical, step-by-step
    CURIOSITY_DISCOVERY = "CURIOSITY_DISCOVERY"          # Dynamic, inquiring hook
    FACT_EMPHASIS = "FACT_EMPHASIS"                      # Deliberate pause, highlighted articulation
    CALM_SUMMARY = "CALM_SUMMARY"                        # Measured, reassuring, consolidating
    REFLECTIVE_CONCLUSION = "REFLECTIVE_CONCLUSION"      # Warm, forward-looking, inspiring


class VoiceDirectionProfile(BaseModel):
    style: DeliveryStyle
    pace_wpm: float
    pause_after_sec: float
    description: str


STYLE_PROFILES: dict[DeliveryStyle, VoiceDirectionProfile] = {
    DeliveryStyle.DOCUMENTARY_NARRATOR: VoiceDirectionProfile(
        style=DeliveryStyle.DOCUMENTARY_NARRATOR,
        pace_wpm=130.0,
        pause_after_sec=0.5,
        description="Standard documentary narration: confident, neutral, clear articulation.",
    ),
    DeliveryStyle.CLASSROOM_TEACHER: VoiceDirectionProfile(
        style=DeliveryStyle.CLASSROOM_TEACHER,
        pace_wpm=135.0,
        pause_after_sec=0.4,
        description="Direct pedagogical tone connecting fundamentals with UPSC exam demands.",
    ),
    DeliveryStyle.SERIOUS_CONSTITUTIONAL: VoiceDirectionProfile(
        style=DeliveryStyle.SERIOUS_CONSTITUTIONAL,
        pace_wpm=120.0,
        pause_after_sec=0.6,
        description="Slower, gravitas-laden tone for landmark judgments, Articles, and rights.",
    ),
    DeliveryStyle.HISTORICAL_STORYTELLING: VoiceDirectionProfile(
        style=DeliveryStyle.HISTORICAL_STORYTELLING,
        pace_wpm=128.0,
        pause_after_sec=0.5,
        description="Narrative pacing for historical background and Constituent Assembly debates.",
    ),
    DeliveryStyle.ANALYTICAL_EXPLANATION: VoiceDirectionProfile(
        style=DeliveryStyle.ANALYTICAL_EXPLANATION,
        pace_wpm=125.0,
        pause_after_sec=0.5,
        description="Measured step-by-step flow for flowcharts, institutional checks, and balances.",
    ),
    DeliveryStyle.CURIOSITY_DISCOVERY: VoiceDirectionProfile(
        style=DeliveryStyle.CURIOSITY_DISCOVERY,
        pace_wpm=140.0,
        pause_after_sec=0.3,
        description="Opening hooks and provocative exam questions to capture attention.",
    ),
    DeliveryStyle.FACT_EMPHASIS: VoiceDirectionProfile(
        style=DeliveryStyle.FACT_EMPHASIS,
        pace_wpm=115.0,
        pause_after_sec=0.7,
        description="High-contrast emphasis on statistics, amendment numbers, and court names.",
    ),
    DeliveryStyle.CALM_SUMMARY: VoiceDirectionProfile(
        style=DeliveryStyle.CALM_SUMMARY,
        pace_wpm=130.0,
        pause_after_sec=0.5,
        description="Recap of Prelims and Mains points with structured consolidation.",
    ),
    DeliveryStyle.REFLECTIVE_CONCLUSION: VoiceDirectionProfile(
        style=DeliveryStyle.REFLECTIVE_CONCLUSION,
        pace_wpm=122.0,
        pause_after_sec=0.8,
        description="Concluding takeaway linking constitutional values with democratic stability.",
    ),
}


class VoiceDirector:
    """Classifies sentence intent and selects appropriate delivery styles and pacing."""

    def select_style_for_text(self, text: str, scene_type: str = "") -> VoiceDirectionProfile:
        lower = text.lower()
        if "article" in lower or "constitution" in lower or "writ" in lower or "supreme court" in lower:
            return STYLE_PROFILES[DeliveryStyle.SERIOUS_CONSTITUTIONAL]
        if "debate" in lower or "history" in lower or "origin" in lower or "framers" in lower:
            return STYLE_PROFILES[DeliveryStyle.HISTORICAL_STORYTELLING]
        if "mechanism" in lower or "step" in lower or "process" in lower or "flowchart" in lower:
            return STYLE_PROFILES[DeliveryStyle.ANALYTICAL_EXPLANATION]
        if "recap" in lower or "summary" in lower or "conclusion" in lower:
            return STYLE_PROFILES[DeliveryStyle.CALM_SUMMARY]
        if "namaste" in lower or "swagat" in lower or "welcome" in lower:
            return STYLE_PROFILES[DeliveryStyle.CURIOSITY_DISCOVERY]

        return STYLE_PROFILES[DeliveryStyle.DOCUMENTARY_NARRATOR]
