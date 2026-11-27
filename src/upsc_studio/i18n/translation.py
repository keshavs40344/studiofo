"""Local-first subtitle/script translation with explicit provider capability checks."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests


LANGUAGE_LABELS = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
}


class TranslationUnavailable(RuntimeError):
    """Raised when no configured local translation provider supports the target language."""


class TranslationService:
    """Use a local LibreTranslate server or optional offline Argos Translate package."""

    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.base_url = os.getenv("UPSC_STUDIO_TRANSLATE_URL", "http://127.0.0.1:5000").rstrip("/")
        self.api_key = os.getenv("UPSC_STUDIO_TRANSLATE_API_KEY")

    def capabilities(self) -> dict[str, Any]:
        try:
            response = self.session.get(f"{self.base_url}/languages", timeout=(2, 3))
            response.raise_for_status()
            languages = response.json()
            codes = {
                str(item.get("code", "")).lower()
                for item in languages if isinstance(item, dict)
            }
            supported = [
                {"code": code, "label": label}
                for code, label in LANGUAGE_LABELS.items()
                if code in codes
            ]
            return {
                "provider": "LIBRETRANSLATE",
                "available": True,
                "supported_languages": supported,
                "configured_url": self.base_url,
                "voice_generation": "SEPARATE_PIPER_VOICE_MODEL_REQUIRED",
            }
        except Exception as libre_error:
            try:
                import argostranslate.translate as argos_translate  # type: ignore[import-not-found]

                installed = argos_translate.get_installed_languages()
                codes = {str(language.code).lower() for language in installed}
                supported = [
                    {"code": code, "label": label}
                    for code, label in LANGUAGE_LABELS.items()
                    if code in codes
                ]
                if supported:
                    return {
                        "provider": "ARGOS_OFFLINE",
                        "available": True,
                        "supported_languages": supported,
                        "configured_url": None,
                        "voice_generation": "SEPARATE_PIPER_VOICE_MODEL_REQUIRED",
                    }
            except Exception:
                pass
            return {
                "provider": None,
                "available": False,
                "supported_languages": [],
                "configured_url": self.base_url,
                "error": f"LibreTranslate unavailable ({type(libre_error).__name__}); Argos offline package/models not installed.",
                "setup": "Start a local LibreTranslate server or install Argos Translate and the required language models.",
            }

    def _translate_one(self, text: str, target_language: str) -> tuple[str, str]:
        target = target_language.lower()
        if target not in LANGUAGE_LABELS:
            raise ValueError(f"Unsupported target language code: {target_language}")
        if not text.strip():
            return text, "NONE"

        caps = self.capabilities()
        if not caps["available"]:
            raise TranslationUnavailable(caps["setup"])

        if caps["provider"] == "LIBRETRANSLATE":
            payload: dict[str, str] = {
                "q": text,
                "source": "auto",
                "target": target,
                "format": "text",
            }
            if self.api_key:
                payload["api_key"] = self.api_key
            response = self.session.post(
                f"{self.base_url}/translate", data=payload, timeout=(5, 45)
            )
            response.raise_for_status()
            translated = str(response.json().get("translatedText") or "").strip()
            if not translated:
                raise TranslationUnavailable("Translation provider returned an empty translation.")
            return translated, "LIBRETRANSLATE"

        import argostranslate.translate as argos_translate  # type: ignore[import-not-found]

        installed = argos_translate.get_installed_languages()
        source_code = os.getenv("UPSC_STUDIO_TRANSLATE_SOURCE_LANG", "en").lower()
        source = next((language for language in installed if language.code == source_code), None)
        target_obj = next((language for language in installed if language.code == target), None)
        if source is None or target_obj is None:
            raise TranslationUnavailable(
                f"Argos translation model {source_code} -> {target} is not installed."
            )
        translation = source.get_translation(target_obj)
        return str(translation.translate(text)), "ARGOS_OFFLINE"

    def translate_segments(self, texts: list[str], target_language: str) -> dict[str, Any]:
        translated: list[str] = []
        provider: str | None = None
        for text in texts:
            result, used_provider = self._translate_one(text, target_language)
            translated.append(result)
            if used_provider != "NONE":
                provider = used_provider
        if provider is None:
            provider = str(self.capabilities().get("provider") or "NONE")
        return {
            "target_language": target_language.lower(),
            "target_language_label": LANGUAGE_LABELS.get(target_language.lower(), target_language),
            "provider": provider,
            "segment_count": len(texts),
            "translated_texts": translated,
            "machine_translation": True,
            "human_language_review_required": True,
            "quality_status": "NOT_HUMAN_REVIEWED",
        }

    def write_translated_script(
        self, project_dir: Path, chapter_title: str, scenes: list[Any],
        translated_texts: list[str], target_language: str, provider: str,
    ) -> Path:
        if len(scenes) != len(translated_texts):
            raise ValueError("Translated segment count must match the scene count.")
        output_dir = project_dir / "teaching" / "translations" / target_language.lower()
        output_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# {chapter_title} — {LANGUAGE_LABELS.get(target_language.lower(), target_language)}",
            "",
            f"- Translation provider: {provider}",
            "- Status: MACHINE_TRANSLATED_NEEDS_HUMAN_LANGUAGE_REVIEW",
            "",
        ]
        for scene, translated in zip(scenes, translated_texts):
            lines.extend([f"## {scene.section_title}", "", translated, ""])
        path = output_dir / "translated_script.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
