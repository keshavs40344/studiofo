"""Nine-stage multilingual lifecycle, translation QA, and dubbing validation manager."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class LanguageStage(str, Enum):
    CATALOGUE_AVAILABLE = "CATALOGUE_AVAILABLE"
    TRANSLATION_PROVIDER_AVAILABLE = "TRANSLATION_PROVIDER_AVAILABLE"
    TRANSLATION_COMPLETED = "TRANSLATION_COMPLETED"
    HUMAN_TRANSLATION_QA_COMPLETED = "HUMAN_TRANSLATION_QA_COMPLETED"
    TARGET_VOICE_INSTALLED = "TARGET_VOICE_INSTALLED"
    VOICE_LICENSING_VERIFIED = "VOICE_LICENSING_VERIFIED"
    DUBBING_GENERATED = "DUBBING_GENERATED"
    AUDIO_QA_COMPLETED = "AUDIO_QA_COMPLETED"
    FINAL_LANGUAGE_TRACK_APPROVED = "FINAL_LANGUAGE_TRACK_APPROVED"


SUPPORTED_CATALOGUE = {
    # Indian Languages
    "hi": {"name": "Hindi", "script": "Devanagari", "region": "North/Central India"},
    "bn": {"name": "Bengali", "script": "Bengali", "region": "West Bengal, Tripura"},
    "ta": {"name": "Tamil", "script": "Tamil", "region": "Tamil Nadu"},
    "te": {"name": "Telugu", "script": "Telugu", "region": "Andhra Pradesh, Telangana"},
    "mr": {"name": "Marathi", "script": "Devanagari", "region": "Maharashtra"},
    "gu": {"name": "Gujarati", "script": "Gujarati", "region": "Gujarat"},
    "kn": {"name": "Kannada", "script": "Kannada", "region": "Karnataka"},
    "ml": {"name": "Malayalam", "script": "Malayalam", "region": "Kerala"},
    "pa": {"name": "Punjabi", "script": "Gurmukhi", "region": "Punjab"},
    "or": {"name": "Odia", "script": "Odia", "region": "Odisha"},
    "as": {"name": "Assamese", "script": "Bengali-Assamese", "region": "Assam"},
    "ur": {"name": "Urdu", "script": "Perso-Arabic", "region": "Jammu & Kashmir, Telangana, UP"},
    "sa": {"name": "Sanskrit", "script": "Devanagari", "region": "Pan-India Classical"},

    # International Languages
    "en": {"name": "English", "script": "Latin", "region": "Global/Pan-India"},
    "es": {"name": "Spanish", "script": "Latin", "region": "Latin America / Europe"},
    "fr": {"name": "French", "script": "Latin", "region": "Europe / Africa"},
}


@dataclass
class LanguageTrackStatus:
    lang_code: str
    language_name: str
    script: str
    current_stage: LanguageStage = LanguageStage.CATALOGUE_AVAILABLE
    translation_provider: Optional[str] = None
    translation_completed_at: Optional[str] = None
    human_translator: Optional[str] = None
    voice_model_name: Optional[str] = None
    voice_license_type: Optional[str] = None
    dubbing_audio_path: Optional[str] = None
    audio_qa_passed: bool = False
    is_ready_for_release: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["current_stage"] = self.current_stage.value
        return d


class MultilingualLifecycleManager:
    """Tracks and enforces the explicit 9-stage progression for all dubbing and subtitle tracks.

    Rule: Never treat a catalogue entry as a completed or release-ready language track.
    """

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.lifecycle_dir = project_dir / "languages"
        self.lifecycle_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_file = self.lifecycle_dir / "multilingual_lifecycle.json"
        self.tracks: dict[str, LanguageTrackStatus] = self._load_or_initialize()

    def _load_or_initialize(self) -> dict[str, LanguageTrackStatus]:
        if self.ledger_file.is_file():
            try:
                data = json.loads(self.ledger_file.read_text(encoding="utf-8"))
                tracks: dict[str, LanguageTrackStatus] = {}
                for code, item in data.get("tracks", {}).items():
                    item_copy = dict(item)
                    stage_str = item_copy.pop("current_stage", LanguageStage.CATALOGUE_AVAILABLE.value)
                    tracks[code] = LanguageTrackStatus(
                        current_stage=LanguageStage(stage_str),
                        **item_copy,
                    )
                return tracks
            except Exception:
                pass

        # Initialize with catalogue entries
        tracks = {}
        for code, info in SUPPORTED_CATALOGUE.items():
            tracks[code] = LanguageTrackStatus(
                lang_code=code,
                language_name=info["name"],
                script=info["script"],
                current_stage=LanguageStage.CATALOGUE_AVAILABLE,
            )
        return tracks

    def advance_stage(
        self,
        lang_code: str,
        target_stage: LanguageStage,
        **kwargs,
    ) -> LanguageTrackStatus:
        """Advance a language track to a target stage with prerequisite verification."""
        code = lang_code.lower().strip()
        if code not in self.tracks:
            raise ValueError(f"Language '{lang_code}' is not in the supported catalogue ({list(SUPPORTED_CATALOGUE.keys())}).")

        track = self.tracks[code]

        # Stage prerequisites enforcement
        if target_stage == LanguageStage.TRANSLATION_COMPLETED:
            if not kwargs.get("translation_provider"):
                raise ValueError("translation_provider is required to mark TRANSLATION_COMPLETED.")
            track.translation_provider = kwargs["translation_provider"]
            track.translation_completed_at = kwargs.get("completed_at")

        elif target_stage == LanguageStage.HUMAN_TRANSLATION_QA_COMPLETED:
            if track.current_stage.value < LanguageStage.TRANSLATION_COMPLETED.value:
                raise ValueError("Cannot perform human QA before TRANSLATION_COMPLETED.")
            if not kwargs.get("human_translator") or len(kwargs["human_translator"].strip()) < 2:
                raise ValueError("A named human translator reviewer is required.")
            track.human_translator = kwargs["human_translator"]

        elif target_stage == LanguageStage.DUBBING_GENERATED:
            if not kwargs.get("voice_model_name"):
                raise ValueError("voice_model_name is required for dubbing generation.")
            if not kwargs.get("dubbing_audio_path"):
                raise ValueError("dubbing_audio_path is required for DUBBING_GENERATED.")
            track.voice_model_name = kwargs["voice_model_name"]
            track.dubbing_audio_path = str(kwargs["dubbing_audio_path"])

        elif target_stage == LanguageStage.AUDIO_QA_COMPLETED:
            if not kwargs.get("audio_qa_passed", False):
                raise ValueError("audio_qa_passed must be True to pass AUDIO_QA_COMPLETED.")
            track.audio_qa_passed = True

        elif target_stage == LanguageStage.FINAL_LANGUAGE_TRACK_APPROVED:
            if not track.audio_qa_passed or not track.human_translator:
                raise ValueError("Cannot approve final track without human translation QA and passed audio QA.")
            track.is_ready_for_release = True

        track.current_stage = target_stage
        if "notes" in kwargs:
            track.notes = kwargs["notes"]

        self.save_ledger()
        return track

    def save_ledger(self) -> Path:
        """Serialize multilingual lifecycle ledger and audit report."""
        data = {
            "supported_catalogue_count": len(SUPPORTED_CATALOGUE),
            "tracks": {code: t.to_dict() for code, t in self.tracks.items()},
        }
        self.ledger_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        # Generate markdown report
        report_lines = [
            "# Multilingual Dubbing & Subtitle Track Lifecycle Report",
            "",
            "| Code | Language | Current Stage | Human QA | Audio QA | Release Ready |",
            "|---|---|---|---|---|---|",
        ]
        for code, t in self.tracks.items():
            report_lines.append(
                f"| `{t.lang_code}` | {t.language_name} | `{t.current_stage.value}` | "
                f"{t.human_translator or 'PENDING'} | {'PASSED' if t.audio_qa_passed else 'PENDING'} | "
                f"{'YES' if t.is_ready_for_release else 'NO'} |"
            )

        (self.lifecycle_dir / "multilingual_qa_report.md").write_text("\n".join(report_lines), encoding="utf-8")
        return self.ledger_file
