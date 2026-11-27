"""Comprehensive pronunciation dictionary, technical term phonetics, and project override engine."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

CORE_PRONUNCIATION_LEXICON: dict[str, str] = {
    # 1. Abbreviations & Acronyms
    "UPSC": "यू पी एस सी",
    "CSE": "सी एस ई",
    "CSAT": "सी सैट",
    "GS-I": "जी एस पेपर वन",
    "GS-II": "जी एस पेपर टू",
    "GS-III": "जी एस पेपर थ्री",
    "GS-IV": "जी एस पेपर फोर",
    "NITI Aayog": "नीति आयोग",
    "RBI": "आर बी आई",
    "CAG": "कैग",
    "ECI": "इलेक्शन कमीशन ऑफ इंडिया",
    "NHRC": "एन एच आर सी",
    "MoSPI": "मॉसपी",
    "SEBI": "सेबी",
    "GST": "जी एस टी",
    "NGT": "एन जी टी",

    # 2. Constitutional & Legal Terminology
    "Constitution": "कॉन्स्टिट्यूशन",
    "Constitutional": "कॉन्स्टिट्यूशनल",
    "Preamble": "प्रिएम्बल",
    "Fundamental Rights": "फंडामेंटल राइट्स",
    "Directive Principles": "डाइरेक्टिव प्रिंसिपल्स",
    "Basic Structure": "बेसिक स्ट्रक्चर",
    "Judicial Review": "ज्यूडिशियल रिव्यू",
    "Article": "आर्टिकल",
    "Articles": "आर्टिकल्स",
    "Schedule": "शेड्यूल",
    "Tenth Schedule": "टेंथ शेड्यूल",
    "Part III": "पार्ट थ्री",
    "Writs": "रिट्स",
    "Habeas Corpus": "हेबियस कॉर्पस",
    "Mandamus": "मैंडेमस",
    "Certiorari": "सर्शियोरारी",
    "Quo Warranto": "को वारंटो",
    "Prohibition": "प्रोहिबिशन",
    "Suo Motu": "सुओ मोटो",
    "Ultra Vires": "अल्ट्रा वायरस",
    "Ratio Decidendi": "रेशियो डेसिडेंडी",
    "Obiter Dicta": "ओबिटर डिक्टा",
    "Amicus Curiae": "एमिकस क्यूरी",
    "Supreme Court": "सुप्रीम कोर्ट",
    "High Court": "हाई कोर्ट",

    # 3. Landmark Case Names
    "K.S. Puttaswamy": "के एस पुट्टास्वामी",
    "Kihoto Hollohan": "किहोतो होलोहन",
    "Kesavananda Bharati": "केशवानंद भारती",
    "Maneka Gandhi": "मेनका गांधी",
    "Minerva Mills": "मिनर्वा मिल्स",
    "Indra Sawhney": "इंद्रा साहनी",

    # 4. Historical Figures & Entities
    "Chandragupta": "चन्द्रगुप्त",
    "Ashoka": "अशोक",
    "Akbar": "अकबर",
    "B.R. Ambedkar": "बी आर अंबेडकर",
    "Bal Gangadhar Tilak": "बाल गंगाधर तिलक",
    "Dadabhai Naoroji": "दादाभाई नौरोजी",
    "Subhas Chandra Bose": "सुभाष चंद्र बोस",
    "Constituent Assembly": "कॉन्स्टिट्यूएंट असेंबली",

    # 5. Geographic Names
    "Tsangpo": "त्सांगपो",
    "Lakshadweep": "लक्षद्वीप",
    "Western Ghats": "वेस्टर्न घाट्स",
    "Coromandel": "कोरोमंडल",
    "Sundarbans": "सुंदरबन",
    "Deccan Plateau": "डेक्कन प्लेटो",
    "Siachen": "सियाचिन",

    # 6. Scientific & Economic Terminology
    "Photosynthesis": "फोटोसिंथेसिस",
    "Chlorophyll": "क्लोरोफिल",
    "Photovoltaic": "फोटोवोल्टाइक",
    "Troposphere": "ट्रोपोस्फीयर",
    "Repo Rate": "रेपो रेट",
    "Fiscal Deficit": "फिस्कल डेफिसिट",
    "Current Account Deficit": "करंट अकाउंट डेफिसिट",
}

# Number and unit pronunciation conversions for clear spoken narration
NUMBER_AND_UNIT_PATTERNS = [
    (r"\b1947\b", "उन्नीस सौ सैंतालीस"),
    (r"\b1950\b", "उन्नीस सौ पचास"),
    (r"\b1976\b", "उन्नीस सौ छिहत्तर"),
    (r"\b1978\b", "उन्नीस सौ अठहत्तर"),
    (r"\b1985\b", "उन्नीस सौ पचासी"),
    (r"\b1991\b", "उन्नीस सौ इक्यानवे"),
    (r"\b2024\b", "दो हज़ार चौबीस"),
    (r"\b2025\b", "दो हज़ार पच्चीस"),
    (r"\b2026\b", "दो हज़ार छब्बीस"),
    (r"\b42nd\b", "बयालीसवां"),
    (r"\b44th\b", "चौवालीसवां"),
    (r"\b52nd\b", "बावनवां"),
    (r"\b73rd\b", "तिहत्तरवां"),
    (r"\b74th\b", "चौहत्तरवां"),
    (r"\b86th\b", "छियासीवां"),
    (r"\b%\b", "प्रतिशत"),
    (r"\bGW\b", "गीगावाट"),
    (r"\bMW\b", "मेगावाट"),
]


class AdvancedPronunciationLexicon:
    """Manages bilingual pronunciation mappings with project-level overrides."""

    def __init__(self, project_dir: Optional[Path] = None, custom_overrides: Optional[dict[str, str]] = None) -> None:
        self.lexicon = dict(CORE_PRONUNCIATION_LEXICON)
        self.project_dir = project_dir

        # Load project-level overrides if present on disk
        if project_dir:
            override_file = project_dir / "tts" / "pronunciation_overrides.json"
            if override_file.is_file():
                try:
                    data = json.loads(override_file.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        self.lexicon.update(data)
                except Exception:
                    pass

        # Apply runtime custom overrides
        if custom_overrides:
            self.lexicon.update(custom_overrides)

    def normalize(self, text: str) -> tuple[str, list[dict[str, str]]]:
        """Normalize terms for natural pronunciation without changing semantic meaning."""
        normalized = text
        applied: list[dict[str, str]] = []

        # 1. Normalize numbers, dates and units
        for pat, replacement in NUMBER_AND_UNIT_PATTERNS:
            if re.search(pat, normalized):
                normalized = re.sub(pat, replacement, normalized)
                applied.append({"pattern": pat, "spoken_form": replacement, "type": "number_or_unit"})

        # 2. Normalize technical, legal, and proper nouns (longest terms first)
        for term in sorted(self.lexicon, key=len, reverse=True):
            replacement = self.lexicon[term]
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
            if pattern.search(normalized):
                normalized = pattern.sub(replacement, normalized)
                applied.append({"term": term, "spoken_form": replacement, "type": "lexicon_term"})

        return normalized, applied

    def save_project_overrides(self, overrides: dict[str, str]) -> Path:
        """Persist project-level pronunciation corrections."""
        if not self.project_dir:
            raise ValueError("project_dir must be configured to save project overrides.")
        out_dir = self.project_dir / "tts"
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / "pronunciation_overrides.json"
        file_path.write_text(json.dumps(overrides, indent=2, ensure_ascii=False), encoding="utf-8")
        self.lexicon.update(overrides)
        return file_path
