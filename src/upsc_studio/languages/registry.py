"""Language Registry, status enums, and locale mapping for multilingual dubbing."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class LanguageStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    EXPERIMENTAL = "EXPERIMENTAL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"


class LanguageProfile(BaseModel):
    code: str  # Model language code (e.g., 'en', 'hi', 'bn')
    name: str  # English name
    native_name: str  # Endonym / Native script name
    youtube_code: str  # BCP-47 tag for YouTube (e.g. 'en-US', 'hi', 'zh-Hans')
    script: str  # Script name (Latin, Devanagari, Bengali, etc.)
    is_indic_scheduled: bool = False  # Whether it's one of the 22 Indian scheduled languages
    translation_provider: str = "m2m100_indictrans2"
    tts_provider: str = "libra_piper_indic"
    available_voices: list[str] = Field(default_factory=list)
    default_voice: str = "narrator_neutral"
    status: LanguageStatus = LanguageStatus.AVAILABLE
    licence_info: str = "Apache-2.0 / MIT / OpenModel"
    pronunciation_qa_status: str = "VERIFIED"
    notes: str = ""


# 16 Primary Target Languages
CORE_16_LANGUAGES: dict[str, LanguageProfile] = {
    "en": LanguageProfile(
        code="en",
        name="English",
        native_name="English",
        youtube_code="en",
        script="Latin",
        is_indic_scheduled=False,
        available_voices=["en_male_narrator", "en_female_narrator", "narrator_neutral"],
        default_voice="en_male_narrator",
        status=LanguageStatus.AVAILABLE,
        notes="Primary educational international language",
    ),
    "hi": LanguageProfile(
        code="hi",
        name="Hindi",
        native_name="हिन्दी",
        youtube_code="hi",
        script="Devanagari",
        is_indic_scheduled=True,
        available_voices=["hi_IN-pratham-medium", "hi_male_documentary", "hi_female_educator"],
        default_voice="hi_IN-pratham-medium",
        status=LanguageStatus.AVAILABLE,
        notes="Primary UPSC examination and instruction medium",
    ),
    "bn": LanguageProfile(
        code="bn",
        name="Bengali",
        native_name="বাংলা",
        youtube_code="bn",
        script="Bengali",
        is_indic_scheduled=True,
        available_voices=["bn_male_documentary", "bn_female_narrator"],
        default_voice="bn_male_documentary",
        status=LanguageStatus.AVAILABLE,
        notes="Major Indian regional language with IndicTrans2/TTS support",
    ),
    "pa": LanguageProfile(
        code="pa",
        name="Punjabi",
        native_name="ਪੰਜਾਬੀ",
        youtube_code="pa",
        script="Gurmukhi",
        is_indic_scheduled=True,
        available_voices=["pa_male_narrator", "pa_female_narrator"],
        default_voice="pa_male_narrator",
        status=LanguageStatus.AVAILABLE,
        notes="Major North-Indian language with Gurmukhi script protection",
    ),
    "ur": LanguageProfile(
        code="ur",
        name="Urdu",
        native_name="اردو",
        youtube_code="ur",
        script="Perso-Arabic",
        is_indic_scheduled=True,
        available_voices=["ur_male_narrator", "ur_female_narrator"],
        default_voice="ur_male_narrator",
        status=LanguageStatus.AVAILABLE,
        notes="Eighth Schedule Indian language, Perso-Arabic right-to-left script",
    ),
    "id": LanguageProfile(
        code="id",
        name="Indonesian",
        native_name="Bahasa Indonesia",
        youtube_code="id",
        script="Latin",
        is_indic_scheduled=False,
        available_voices=["id_male_narrator", "id_female_narrator"],
        default_voice="id_male_narrator",
        status=LanguageStatus.AVAILABLE,
        notes="ASEAN core international demographic",
    ),
    "ar": LanguageProfile(
        code="ar",
        name="Arabic",
        native_name="العربية",
        youtube_code="ar",
        script="Arabic",
        is_indic_scheduled=False,
        available_voices=["ar_male_narrator", "ar_female_narrator"],
        default_voice="ar_male_narrator",
        status=LanguageStatus.AVAILABLE,
        notes="Right-to-left international UN language",
    ),
    "es": LanguageProfile(
        code="es",
        name="Spanish",
        native_name="Español",
        youtube_code="es",
        script="Latin",
        is_indic_scheduled=False,
        available_voices=["es_male_narrator", "es_female_narrator"],
        default_voice="es_male_narrator",
        status=LanguageStatus.AVAILABLE,
        notes="Global international language (Latin America, Spain)",
    ),
    "fr": LanguageProfile(
        code="fr",
        name="French",
        native_name="Français",
        youtube_code="fr",
        script="Latin",
        is_indic_scheduled=False,
        available_voices=["fr_male_narrator", "fr_female_narrator"],
        default_voice="fr_male_narrator",
        status=LanguageStatus.AVAILABLE,
        notes="UN diplomatic & Francophone international reach",
    ),
    "de": LanguageProfile(
        code="de",
        name="German",
        native_name="Deutsch",
        youtube_code="de",
        script="Latin",
        is_indic_scheduled=False,
        available_voices=["de_male_narrator", "de_female_narrator"],
        default_voice="de_male_narrator",
        status=LanguageStatus.AVAILABLE,
        notes="Central European academic & technical audience",
    ),
    "it": LanguageProfile(
        code="it",
        name="Italian",
        native_name="Italiano",
        youtube_code="it",
        script="Latin",
        is_indic_scheduled=False,
        available_voices=["it_male_narrator", "it_female_narrator"],
        default_voice="it_male_narrator",
        status=LanguageStatus.AVAILABLE,
        notes="European international language",
    ),
    "pt": LanguageProfile(
        code="pt",
        name="Portuguese",
        native_name="Português",
        youtube_code="pt-BR",
        script="Latin",
        is_indic_scheduled=False,
        available_voices=["pt_male_narrator", "pt_female_narrator"],
        default_voice="pt_male_narrator",
        status=LanguageStatus.AVAILABLE,
        notes="Brazil, Portugal & Lusophone demographic",
    ),
    "ru": LanguageProfile(
        code="ru",
        name="Russian",
        native_name="Русский",
        youtube_code="ru",
        script="Cyrillic",
        is_indic_scheduled=False,
        available_voices=["ru_male_narrator", "ru_female_narrator"],
        default_voice="ru_male_narrator",
        status=LanguageStatus.AVAILABLE,
        notes="Cyrillic UN international language",
    ),
    "zh": LanguageProfile(
        code="zh",
        name="Chinese (Simplified)",
        native_name="中文",
        youtube_code="zh-Hans",
        script="Simplified Han",
        is_indic_scheduled=False,
        available_voices=["zh_male_narrator", "zh_female_narrator"],
        default_voice="zh_male_narrator",
        status=LanguageStatus.AVAILABLE,
        notes="East Asian UN language with Han character mapping",
    ),
    "ja": LanguageProfile(
        code="ja",
        name="Japanese",
        native_name="日本語",
        youtube_code="ja",
        script="Kanji/Kana",
        is_indic_scheduled=False,
        available_voices=["ja_male_narrator", "ja_female_narrator"],
        default_voice="ja_male_narrator",
        status=LanguageStatus.AVAILABLE,
        notes="East Asian international language",
    ),
    "ko": LanguageProfile(
        code="ko",
        name="Korean",
        native_name="한국어",
        youtube_code="ko",
        script="Hangul",
        is_indic_scheduled=False,
        available_voices=["ko_male_narrator", "ko_female_narrator"],
        default_voice="ko_male_narrator",
        status=LanguageStatus.AVAILABLE,
        notes="East Asian Hangul phonetic script",
    ),
}

# Indian Regional Extension (22 Scheduled Languages)
INDIAN_REGIONAL_EXTENSION: dict[str, LanguageProfile] = {
    "ta": LanguageProfile(
        code="ta", name="Tamil", native_name="தமிழ்", youtube_code="ta", script="Tamil",
        is_indic_scheduled=True, status=LanguageStatus.EXPERIMENTAL, notes="Indic regional track"
    ),
    "te": LanguageProfile(
        code="te", name="Telugu", native_name="తెలుగు", youtube_code="te", script="Telugu",
        is_indic_scheduled=True, status=LanguageStatus.EXPERIMENTAL, notes="Indic regional track"
    ),
    "mr": LanguageProfile(
        code="mr", name="Marathi", native_name="मराठी", youtube_code="mr", script="Devanagari",
        is_indic_scheduled=True, status=LanguageStatus.EXPERIMENTAL, notes="Indic regional track"
    ),
    "gu": LanguageProfile(
        code="gu", name="Gujarati", native_name="ગુજરાતી", youtube_code="gu", script="Gujarati",
        is_indic_scheduled=True, status=LanguageStatus.EXPERIMENTAL, notes="Indic regional track"
    ),
    "kn": LanguageProfile(
        code="kn", name="Kannada", native_name="ಕನ್ನಡ", youtube_code="kn", script="Kannada",
        is_indic_scheduled=True, status=LanguageStatus.EXPERIMENTAL, notes="Indic regional track"
    ),
    "ml": LanguageProfile(
        code="ml", name="Malayalam", native_name="മലയാളം", youtube_code="ml", script="Malayalam",
        is_indic_scheduled=True, status=LanguageStatus.EXPERIMENTAL, notes="Indic regional track"
    ),
    "or": LanguageProfile(
        code="or", name="Odia", native_name="ଓଡ଼ିଆ", youtube_code="or", script="Odia",
        is_indic_scheduled=True, status=LanguageStatus.EXPERIMENTAL, notes="Indic regional track"
    ),
    "as": LanguageProfile(
        code="as", name="Assamese", native_name="অসমীয়া", youtube_code="as", script="Bengali-Assamese",
        is_indic_scheduled=True, status=LanguageStatus.EXPERIMENTAL, notes="Indic regional track"
    ),
    "sa": LanguageProfile(
        code="sa", name="Sanskrit", native_name="संस्कृतम्", youtube_code="sa", script="Devanagari",
        is_indic_scheduled=True, status=LanguageStatus.EXPERIMENTAL, notes="Classical constitutional language"
    ),
    "ne": LanguageProfile(
        code="ne", name="Nepali", native_name="नेपाली", youtube_code="ne", script="Devanagari",
        is_indic_scheduled=True, status=LanguageStatus.EXPERIMENTAL, notes="Indic regional track"
    ),
    "kok": LanguageProfile(
        code="kok", name="Konkani", native_name="कोंकणी", youtube_code="kok", script="Devanagari",
        is_indic_scheduled=True, status=LanguageStatus.REVIEW_REQUIRED, notes="Indic regional track"
    ),
    "mni": LanguageProfile(
        code="mni", name="Manipuri", native_name="মৈতৈলোন্", youtube_code="mni", script="Meitei/Bengali",
        is_indic_scheduled=True, status=LanguageStatus.REVIEW_REQUIRED, notes="Indic regional track"
    ),
    "brx": LanguageProfile(
        code="brx", name="Bodo", native_name="बर'", youtube_code="brx", script="Devanagari",
        is_indic_scheduled=True, status=LanguageStatus.REVIEW_REQUIRED, notes="Indic regional track"
    ),
    "dgo": LanguageProfile(
        code="dgo", name="Dogri", native_name="डोगरी", youtube_code="dgo", script="Devanagari",
        is_indic_scheduled=True, status=LanguageStatus.REVIEW_REQUIRED, notes="Indic regional track"
    ),
    "mai": LanguageProfile(
        code="mai", name="Maithili", native_name="मैथिली", youtube_code="mai", script="Devanagari",
        is_indic_scheduled=True, status=LanguageStatus.REVIEW_REQUIRED, notes="Indic regional track"
    ),
    "sat": LanguageProfile(
        code="sat", name="Santali", native_name="ᱥᱟᱱᱛᱟᱲᱤ", youtube_code="sat", script="Ol Chiki",
        is_indic_scheduled=True, status=LanguageStatus.REVIEW_REQUIRED, notes="Indic regional track"
    ),
    "sd": LanguageProfile(
        code="sd", name="Sindhi", native_name="سنڌي", youtube_code="sd", script="Perso-Arabic",
        is_indic_scheduled=True, status=LanguageStatus.REVIEW_REQUIRED, notes="Indic regional track"
    ),
}


class LanguageRegistry:
    """Provides querying, validation, and metadata mapping for 16 core + Indian extension languages."""

    def __init__(self, include_regional_extension: bool = True) -> None:
        self.languages: dict[str, LanguageProfile] = {**CORE_16_LANGUAGES}
        if include_regional_extension:
            self.languages.update(INDIAN_REGIONAL_EXTENSION)

    def get(self, code: str) -> Optional[LanguageProfile]:
        return self.languages.get(code.lower())

    def list_core_16(self) -> list[LanguageProfile]:
        return [self.languages[c] for c in CORE_16_LANGUAGES]

    def list_all(self) -> list[LanguageProfile]:
        return list(self.languages.values())

    def list_indic_languages(self) -> list[LanguageProfile]:
        return [lp for lp in self.languages.values() if lp.is_indic_scheduled]

    def get_youtube_code(self, code: str) -> str:
        lp = self.get(code)
        return lp.youtube_code if lp else code

    def is_supported(self, code: str) -> bool:
        lp = self.get(code)
        return lp is not None and lp.status in {LanguageStatus.AVAILABLE, LanguageStatus.EXPERIMENTAL}
