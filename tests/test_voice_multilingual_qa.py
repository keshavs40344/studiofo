"""Audio quality diagnostics, pronunciation intelligence, and multilingual lifecycle test suite.

Tests:
- Corrupt audio detection
- Incorrect sample rate detection
- Clipping detection
- Excessive silence detection
- Subtitle line-splitting and drift detection
- Pronunciation lexicon and project-level overrides
- Missing translation provider handling
- Missing voice model handling
- Multilingual 9-stage lifecycle enforcement
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
import pytest

from upsc_studio.audio.quality import AudioQualityInspector
from upsc_studio.audio.subtitles import SubtitleCue, SubtitleEngine
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, SceneSpec
from upsc_studio.i18n.translation import TranslationService, TranslationUnavailable
from upsc_studio.languages.lifecycle import (
    LanguageStage,
    MultilingualLifecycleManager,
    SUPPORTED_CATALOGUE,
)
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.tts.adapter import PiperTTSEngine
from upsc_studio.tts.pronunciation_lexicon import AdvancedPronunciationLexicon


def _create_wav(
    path: Path,
    samples: list[float],
    sample_rate: int = 44100,
) -> Path:
    """Helper to synthesize uncompressed 16-bit PCM WAV fixtures."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        int_samples = [max(-32768, min(32767, int(s * 32767.0))) for s in samples]
        raw_data = struct.pack(f"<{len(int_samples)}h", *int_samples)
        wf.writeframes(raw_data)
    return path


def test_corrupt_audio_rejection(tmp_path: Path) -> None:
    """AudioQualityInspector must flag corrupt or truncated audio files as FAILED."""
    corrupt_file = tmp_path / "corrupt.wav"
    corrupt_file.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00invalid-bytes")

    report = AudioQualityInspector.inspect_wav(corrupt_file)
    assert report.quality_status == "FAILED"
    assert report.is_valid_format is False
    assert any("Corrupt or invalid" in issue for issue in report.issues)


def test_incorrect_sample_rate_detection(tmp_path: Path) -> None:
    """Recordings with sub-standard sample rates (< 44.1 kHz) must be flagged."""
    low_rate_file = tmp_path / "low_rate.wav"
    # 1.0 second of 16 kHz audio
    samples = [0.3 * math.sin(2 * math.pi * 440 * i / 16000) for i in range(16000)]
    _create_wav(low_rate_file, samples, sample_rate=16000)

    report = AudioQualityInspector.inspect_wav(low_rate_file)
    assert report.sample_rate == 16000
    assert any("below recommended broadcast standard" in issue for issue in report.issues)


def test_clipping_detection(tmp_path: Path) -> None:
    """Audio containing samples that exceed clipping threshold must be flagged as clipped."""
    clipped_file = tmp_path / "clipped.wav"
    # Audio with deliberate hard clipping (amplitude 1.0)
    samples = [1.0 if (i % 20 < 10) else -1.0 for i in range(44100)]
    _create_wav(clipped_file, samples, sample_rate=44100)

    report = AudioQualityInspector.inspect_wav(clipped_file)
    assert report.is_clipped is True
    assert report.clipping_sample_count > 10
    assert any("Clipping detected" in issue for issue in report.issues)


def test_excessive_silence_detection(tmp_path: Path) -> None:
    """Recordings containing prolonged dead air (> 3.0s) must be flagged."""
    silence_file = tmp_path / "excessive_silence.wav"
    # 0.5s active + 3.5s pure silence + 0.5s active = 4.5s total
    rate = 44100
    active_samples = [0.4 * math.sin(2 * math.pi * 440 * i / rate) for i in range(int(rate * 0.5))]
    silent_samples = [0.0] * int(rate * 3.5)
    samples = active_samples + silent_samples + active_samples
    _create_wav(silence_file, samples, sample_rate=rate)

    report = AudioQualityInspector.inspect_wav(silence_file)
    assert report.has_excessive_silence is True
    assert report.max_silence_gap_sec >= 3.4
    assert any("Excessive dead air" in issue for issue in report.issues)


def test_clean_audio_inspection_passes(tmp_path: Path) -> None:
    """Broadcast-quality speech audio must pass inspection with zero defects."""
    clean_file = tmp_path / "clean_voice.wav"
    rate = 44100
    # Clean 2.0s signal, peak amplitude 0.6, no prolonged silence
    samples = [0.6 * math.sin(2 * math.pi * 300 * i / rate) for i in range(rate * 2)]
    _create_wav(clean_file, samples, sample_rate=rate)

    report = AudioQualityInspector.inspect_wav(clean_file)
    assert report.quality_status == "PASSED"
    assert report.is_clipped is False
    assert report.has_excessive_silence is False
    assert len(report.issues) == 0


def test_subtitle_line_splitting_and_drift_detection(tmp_path: Path) -> None:
    """Subtitles must be split to <= 42 chars per line, max 2 lines, and drift-free."""
    engine = SubtitleEngine()

    long_sentence = (
        "The Supreme Court of India exercises original jurisdiction under Article 32 "
        "to enforce the Fundamental Rights guaranteed to citizens."
    )
    split_lines = engine.split_into_readable_lines(long_sentence)
    lines = split_lines.split("\n")
    assert len(lines) <= 2
    assert all(len(line) <= 42 for line in lines)

    # Test alignment with SceneSpec
    scenes = [
        SceneSpec(
            scene_id="SCN_01", section_id="SEC_01", section_title="Introduction",
            learning_objective="Understand writs", narration_text=long_sentence,
            estimated_duration_sec=6.0, visual_category="Concept Card", on_screen_title="Writs",
        )
    ]
    cues = engine.align_scenes_to_cues(scenes, actual_audio_duration_sec=6.0)
    assert len(cues) >= 1

    # Verify SRT and VTT export
    srt_path = tmp_path / "subs.srt"
    vtt_path = tmp_path / "subs.vtt"
    engine.write_srt(cues, srt_path)
    engine.write_vtt(cues, vtt_path)
    assert srt_path.exists()
    assert vtt_path.exists()
    assert "-->" in srt_path.read_text(encoding="utf-8")
    assert "WEBVTT" in vtt_path.read_text(encoding="utf-8")

    # Quality Inspection on valid cues
    qa = engine.inspect_cues_quality(cues)
    assert qa.is_valid is True
    assert qa.has_overlaps is False

    # Intentionally corrupt cue timing (overlapping cues)
    corrupt_cues = [
        SubtitleCue(index=1, start_sec=0.0, end_sec=3.0, text="First cue"),
        SubtitleCue(index=2, start_sec=2.5, end_sec=5.0, text="Overlapping cue"),
    ]
    corrupt_qa = engine.inspect_cues_quality(corrupt_cues)
    assert corrupt_qa.is_valid is False
    assert corrupt_qa.has_overlaps is True


def test_advanced_pronunciation_lexicon_and_project_overrides(tmp_path: Path) -> None:
    """Pronunciation normalizer must correctly transcribe legal terms, numbers, and honor project overrides."""
    lexicon = AdvancedPronunciationLexicon(project_dir=tmp_path)

    # Standard terms and numbers
    text = "In 1947, UPSC conducted examinations under Article 32 concerning Habeas Corpus."
    normalized, applied = lexicon.normalize(text)
    assert "उन्नीस सौ सैंतालीस" in normalized
    assert "यू पी एस सी" in normalized
    assert "आर्टिकल" in normalized
    assert "हेबियस कॉर्पस" in normalized
    assert len(applied) >= 4

    # Project override
    overrides = {"UPSC": "यूनियन पब्लिक सर्विस कमीशन"}
    lexicon.save_project_overrides(overrides)

    # Re-normalize with saved project overrides
    reloaded_lexicon = AdvancedPronunciationLexicon(project_dir=tmp_path)
    norm2, app2 = reloaded_lexicon.normalize("UPSC results declared.")
    assert "यूनियन पब्लिक सर्विस कमीशन" in norm2


def test_missing_translation_provider_handling() -> None:
    """When translation service is unavailable, it must raise TranslationUnavailable with actionable setup."""
    service = TranslationService()
    # Query capabilities without active local translation server
    caps = service.capabilities()
    # When server is not running on 127.0.0.1:5000 and Argos is uninstalled, it reports limitation
    if not caps["available"]:
        with pytest.raises(TranslationUnavailable):
            service._translate_one("Hello world", "hi")


def test_missing_voice_model_handling(tmp_path: Path) -> None:
    """PiperTTSEngine must fail closed when requested voice models are uninstalled or mismatched."""
    engine = PiperTTSEngine(project_dir=tmp_path)
    scene = SceneSpec(
        scene_id="SCN_01", section_id="SEC_01", section_title="Intro",
        learning_objective="Intro", narration_text="Hello", estimated_duration_sec=3.0,
        visual_category="Slide", on_screen_title="Intro",
    )

    # 1. Non-existent model path raises FileNotFoundError or ValueError
    with pytest.raises((FileNotFoundError, ValueError)):
        engine.synthesize_translated_scenes(
            project_id="PRJ_TEST",
            scenes=[scene],
            translated_texts=["வணக்கம்"],
            language_code="ta",
            model_path=tmp_path / "tamil_missing.onnx",
        )


def test_multilingual_9_stage_lifecycle_enforcement(tmp_path: Path) -> None:
    """The multilingual lifecycle manager must strictly enforce 9 distinct stages."""
    mgr = MultilingualLifecycleManager(tmp_path)
    assert len(mgr.tracks) == len(SUPPORTED_CATALOGUE)

    # Initial state is CATALOGUE_AVAILABLE, never marked as completed
    bengali_track = mgr.tracks["bn"]
    assert bengali_track.current_stage == LanguageStage.CATALOGUE_AVAILABLE
    assert bengali_track.is_ready_for_release is False

    # Cannot skip directly to FINAL_LANGUAGE_TRACK_APPROVED without intermediate gates
    with pytest.raises(ValueError, match="Cannot approve final track without human translation QA"):
        mgr.advance_stage("bn", LanguageStage.FINAL_LANGUAGE_TRACK_APPROVED)

    # Valid progression
    # Step 1 -> 3: Translation Completed
    mgr.advance_stage("bn", LanguageStage.TRANSLATION_COMPLETED, translation_provider="LIBRETRANSLATE")
    assert mgr.tracks["bn"].current_stage == LanguageStage.TRANSLATION_COMPLETED

    # Step 4: Human Translation QA
    mgr.advance_stage("bn", LanguageStage.HUMAN_TRANSLATION_QA_COMPLETED, human_translator="Academic Linguist")
    assert mgr.tracks["bn"].current_stage == LanguageStage.HUMAN_TRANSLATION_QA_COMPLETED

    # Step 7: Dubbing Generated
    fake_audio = tmp_path / "dub_bn.wav"
    fake_audio.write_bytes(b"audio-data")
    mgr.advance_stage(
        "bn",
        LanguageStage.DUBBING_GENERATED,
        voice_model_name="piper_bn_academic",
        dubbing_audio_path=fake_audio,
    )

    # Step 8: Audio QA
    mgr.advance_stage("bn", LanguageStage.AUDIO_QA_COMPLETED, audio_qa_passed=True)

    # Step 9: Final Approval
    mgr.advance_stage("bn", LanguageStage.FINAL_LANGUAGE_TRACK_APPROVED)
    assert mgr.tracks["bn"].is_ready_for_release is True

    # Check persisted ledger and report
    ledger_file = tmp_path / "languages" / "multilingual_lifecycle.json"
    report_file = tmp_path / "languages" / "multilingual_qa_report.md"
    assert ledger_file.exists()
    assert report_file.exists()
    assert "bn" in report_file.read_text(encoding="utf-8")
