"""Comprehensive Multilingual Pronunciation Engine and Protected Terminology Lexicon."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional


# Protected terms across constitutional, legal, judicial and numerical categories
PROTECTED_LEGAL_TERMS: list[str] = [
    "Article 12", "Article 13", "Article 14", "Article 19", "Article 21", "Article 32",
    "Article 226", "Part III", "Tenth Schedule", "52nd Amendment", "44th Amendment",
    "Supreme Court", "High Court", "Habeas Corpus", "Mandamus", "Certiorari",
    "Quo Warranto", "Prohibition", "Maneka Gandhi", "Kesavananda Bharati", "Kihoto Hollohan",
    "UPSC", "Prelims", "Mains", "General Studies", "GS-I", "GS-II", "GS-III", "GS-IV",
]

# Multilingual Phonetic Normalization Dictionaries
# Maps technical/legal terms to natural pronunciation for each language's TTS engine
MULTILINGUAL_LEXICONS: dict[str, dict[str, str]] = {
    "hi": {
        "UPSC": "यू पी एस सी",
        "GS-I": "जी एस पेपर वन",
        "GS-II": "जी एस पेपर टू",
        "GS-III": "जी एस पेपर थ्री",
        "GS-IV": "जी एस पेपर फोर",
        "Fundamental Rights": "मौलिक अधिकार",
        "Article": "अनुच्छेद",
        "Articles": "अनुच्छेद",
        "Supreme Court": "उच्चतम न्यायालय",
        "High Court": "उच्च न्यायालय",
        "Constitution": "संविधान",
        "Constitutional": "संवैधानिक",
        "Habeas Corpus": "बंदी प्रत्यक्षीकरण",
        "Mandamus": "परमादेश",
        "Certiorari": "उत्प्रेषण",
        "Quo Warranto": "अधिकार पृच्छा",
        "Prohibition": "प्रतिषेध",
        "Writs": "रिट याचिकाएं",
        "Part III": "भाग तीन",
    },
    "bn": {
        "UPSC": "ইউ পি এস সি",
        "GS-II": "জি এস পেপার দুই",
        "Fundamental Rights": "মৌলিক অধিকার",
        "Article": "অনুচ্ছেদ",
        "Supreme Court": "সুপ্রিম কোর্ট",
        "Constitution": "সংবিধান",
        "Writs": "রিট",
        "Part III": "ভাগ তিন",
    },
    "pa": {
        "UPSC": "ਯੂ ਪੀ ਐਸ ਸੀ",
        "GS-II": "ਜੀ ਐਸ ਪੇਪਰ ਦੋ",
        "Fundamental Rights": "ਮੌਲਿਕ ਅਧਿਕਾਰ",
        "Article": "ਧਾਰਾ",
        "Supreme Court": "ਸੁਪਰੀਮ ਕੋਰਟ",
        "Constitution": "ਸੰਵਿਧਾਨ",
    },
    "ur": {
        "UPSC": "یو پی ایس سی",
        "GS-II": "جی ایس پیپر دوم",
        "Fundamental Rights": "بنیادی حقوق",
        "Article": "دفعہ",
        "Supreme Court": "سپریم کورٹ",
        "Constitution": "آئین",
    },
    "en": {
        "GS-I": "General Studies Paper One",
        "GS-II": "General Studies Paper Two",
        "GS-III": "General Studies Paper Three",
        "GS-IV": "General Studies Paper Four",
        "UPSC": "U.P.S.C.",
        "AIR": "All India Reporter",
        "SC": "Supreme Court",
    },
    "es": {
        "UPSC": "Comisión de Servicios Públicos",
        "Fundamental Rights": "Derechos Fundamentales",
        "Supreme Court": "Corte Suprema",
        "Constitution": "Constitución",
        "Article": "Artículo",
    },
    "fr": {
        "UPSC": "Commission de la fonction publique",
        "Fundamental Rights": "Droits Fondamentaux",
        "Supreme Court": "Cour Suprême",
        "Constitution": "Constitution",
        "Article": "Article",
    },
    "de": {
        "Fundamental Rights": "Grundrechte",
        "Supreme Court": "Oberster Gerichtshof",
        "Constitution": "Verfassung",
        "Article": "Artikel",
    },
    "ru": {
        "Fundamental Rights": "Основные права",
        "Supreme Court": "Верховный суд",
        "Constitution": "Конституция",
        "Article": "Статья",
    },
    "zh": {
        "Fundamental Rights": "基本权利",
        "Supreme Court": "最高法院",
        "Constitution": "宪法",
        "Article": "第",
    },
    "ar": {
        "Fundamental Rights": "الحقوق الأساسية",
        "Supreme Court": "المحكمة العليا",
        "Constitution": "الدستور",
        "Article": "المادة",
    },
}


class MultilingualPronunciationEngine:
    """Provides terminology protection, phonetic normalization, and pronunciation QA reports."""

    def __init__(self, project_dir: Optional[Path] = None) -> None:
        self.project_dir = project_dir
        self.lexicons = {**MULTILINGUAL_LEXICONS}
        self._load_project_overrides()

    def _load_project_overrides(self) -> None:
        if self.project_dir:
            custom_path = self.project_dir / "research" / "custom_pronunciation_lexicon.json"
            if custom_path.exists():
                try:
                    overrides = json.loads(custom_path.read_text(encoding="utf-8"))
                    for lang, terms in overrides.items():
                        self.lexicons.setdefault(lang, {}).update(terms)
                except Exception:
                    pass

    def normalize(self, text: str, lang_code: str) -> tuple[str, list[dict[str, str]]]:
        """Normalize specialized terms for the given language TTS without altering meaning."""
        lang_dict = self.lexicons.get(lang_code.lower(), {})
        normalized = text
        applied: list[dict[str, str]] = []

        # Sort longest keys first to prevent partial replacements
        for term in sorted(lang_dict, key=len, reverse=True):
            replacement = lang_dict[term]
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
            if pattern.search(normalized):
                normalized = pattern.sub(replacement, normalized)
                applied.append({"term": term, "spoken_form": replacement, "language": lang_code})

        return normalized, applied

    def audit_pronunciation(self, text: str, lang_code: str) -> dict[str, Any]:
        """Audit text for tricky terms, numbers, abbreviations, and case citations."""
        abbreviations = re.findall(r"\b[A-Z]{2,}\b", text)
        numbers = re.findall(r"\b\d+(?:st|nd|rd|th)?\b", text)
        legal_refs = [term for term in PROTECTED_LEGAL_TERMS if term.lower() in text.lower()]

        normalized_sample, applied = self.normalize(text, lang_code)
        unhandled_abbrevs = [a for a in abbreviations if a not in self.lexicons.get(lang_code, {})]

        status = "VERIFIED" if len(unhandled_abbrevs) <= 2 else "REVIEW_RECOMMENDED"
        return {
            "language": lang_code,
            "status": status,
            "legal_terms_detected": legal_refs,
            "numbers_detected": numbers[:10],
            "abbreviations_detected": abbreviations,
            "unhandled_abbreviations": unhandled_abbrevs,
            "applied_normalizations_count": len(applied),
        }
