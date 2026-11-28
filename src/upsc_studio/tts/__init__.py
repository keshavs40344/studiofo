"""Built-in licensed AI TTS subsystem (CPU-safe Piper + Windows SAPI fallback)."""

from upsc_studio.tts.pronunciation import PronunciationNormalizer
from upsc_studio.tts.pronunciation_lexicon import (
    AdvancedPronunciationLexicon,
    CORE_PRONUNCIATION_LEXICON,
)

USER_VOICE_REQUIRED = False
AI_NARRATION_ENABLED = True
VOICE_CLONING_ENABLED = False
DEFAULT_NARRATION_LANGUAGE = "Hindi/Hinglish"
DEFAULT_NARRATOR_STYLE = "Neutral Documentary Educational Narrator"

__all__ = [
    "AI_NARRATION_ENABLED",
    "AdvancedPronunciationLexicon",
    "CORE_PRONUNCIATION_LEXICON",
    "DEFAULT_NARRATION_LANGUAGE",
    "DEFAULT_NARRATOR_STYLE",
    "PronunciationNormalizer",
    "USER_VOICE_REQUIRED",
    "VOICE_CLONING_ENABLED",
]
