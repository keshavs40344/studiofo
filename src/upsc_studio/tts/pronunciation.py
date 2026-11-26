"""Pronunciation dictionary and Hindi-English code-mixed normalizer for TTS."""

from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULT_LEXICON: dict[str, str] = {
    "UPSC": "यू पी एस सी",
    "GS-I": "जी एस पेपर वन",
    "GS-II": "जी एस पेपर टू",
    "GS-III": "जी एस पेपर थ्री",
    "GS-IV": "जी एस पेपर फोर",
    "Fundamental Rights": "फंडामेंटल राइट्स",
    "Article": "आर्टिकल",
    "Articles": "आर्टिकल्स",
    "Supreme Court": "सुप्रीम कोर्ट",
    "High Court": "हाई कोर्ट",
    "Constitution": "कॉन्स्टिट्यूशन",
    "Constitutional": "कॉन्स्टिट्यूशनल",
    "K.S. Puttaswamy": "के एस पुट्टास्वामी",
    "Kihoto Hollohan": "किहोतो होलोहन",
    "Habeas Corpus": "हेबियस कॉर्पस",
    "Mandamus": "मैंडेमस",
    "Certiorari": "सर्शियोरारी",
    "Quo Warranto": "को वारंटो",
    "Mains": "मेन्स",
    "Prelims": "प्रीलिम्स",
    "Right to Privacy": "राइट टू प्राइवेसी",
    "Judicial Review": "ज्यूडिशियल रिव्यू",
    "Writs": "रिट्स",
    "Part III": "पार्ट थ्री",
}


class PronunciationNormalizer:
    """Normalizes Hinglish/English technical terms for natural Hindi TTS without altering meaning."""

    def __init__(self, extra_lexicon: dict[str, str] | None = None) -> None:
        self.lexicon = {**DEFAULT_LEXICON, **(extra_lexicon or {})}

    def normalize(self, text: str) -> tuple[str, list[dict]]:
        normalized = text
        applied: list[dict] = []
        # Sort longest keys first to avoid partial replacements
        for term in sorted(self.lexicon, key=len, reverse=True):
            replacement = self.lexicon[term]
            pattern = re.compile(rf"\b{re.escape(term)}\b")
            if pattern.search(normalized):
                normalized = pattern.sub(replacement, normalized)
                applied.append({"term": term, "spoken_form": replacement})
        return normalized, applied

    def save_report(self, out_path: Path, segment_reports: list[dict]) -> Path:
        report = {
            "lexicon_size": len(self.lexicon),
            "segments_processed": len(segment_reports),
            "segments": segment_reports,
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return out_path
