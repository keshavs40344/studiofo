"""Automated unit and integration test suite for Phase 18 Multilingual Dubbing & Dub Pack."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from upsc_studio.languages.registry import LanguageRegistry, LanguageStatus, CORE_16_LANGUAGES
from upsc_studio.languages.pronunciation import MultilingualPronunciationEngine
from upsc_studio.languages.translation import MultilingualTranslationEngine, ScriptSegment
from upsc_studio.languages.subtitles import AudioAwareSubtitleSynchronizer
from upsc_studio.tts.voice_direction import VoiceDirector, DeliveryStyle
from upsc_studio.tts.multilingual_engine import MultilingualTTSEngine
from upsc_studio.publishing.dub_pack import YouTubeDubPackBuilder
from upsc_studio.publishing.youtube_publisher import YouTubePublisher


def test_language_registry_16_core_languages() -> None:
    reg = LanguageRegistry(include_regional_extension=True)
    core = reg.list_core_16()
    assert len(core) == 16
    codes = {c.code for c in core}
    expected = {"en", "hi", "bn", "pa", "ur", "id", "ar", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko"}
    assert codes == expected

    # Verify BCP-47 tags
    assert reg.get_youtube_code("en") == "en"
    assert reg.get_youtube_code("zh") == "zh-Hans"
    assert reg.get_youtube_code("pt") == "pt-BR"

    # Indian Regional Extension exists
    indic = reg.list_indic_languages()
    assert len(indic) >= 15  # hi, bn, pa, ur, ta, te, mr, gu, kn, ml, or, as, sa, ne, etc.


def test_pronunciation_engine_normalization(tmp_path: Path) -> None:
    pron = MultilingualPronunciationEngine(tmp_path)
    # Hindi normalization
    norm_hi, applied_hi = pron.normalize("Under Article 32, Supreme Court issues Writs.", "hi")
    assert "अनुच्छेद" in norm_hi
    assert "उच्चतम न्यायालय" in norm_hi
    assert "रिट याचिकाएं" in norm_hi
    assert len(applied_hi) >= 3

    # Bengali normalization
    norm_bn, applied_bn = pron.normalize("In GS-II, Fundamental Rights are vital.", "bn")
    assert "মৌলিক অধিকার" in norm_bn

    # Audit report
    audit = pron.audit_pronunciation("In 1978, Supreme Court decided Maneka Gandhi under Article 21.", "hi")
    assert audit["status"] == "VERIFIED"
    assert "Article 21" in audit["legal_terms_detected"] or "Supreme Court" in audit["legal_terms_detected"]


def test_translation_engine_and_qa_preserves_numbers_and_terms(tmp_path: Path) -> None:
    trans_engine = MultilingualTranslationEngine(tmp_path)
    title = "Fundamental Rights: Scope, Writs, and Judicial Review"

    # Translates across multiple languages
    hi_title = trans_engine.translate_text(title, "en", "hi")
    assert "मौलिक अधिकार" in hi_title

    es_title = trans_engine.translate_text(title, "en", "es")
    assert "Derechos Fundamentales" in es_title

    # QA checks number preservation
    source_clause = "The 52nd Amendment of 1985 inserted Article 102."
    translated_ok = "1985 ka 52nd Amendment ne Article 102 add kiya."
    qa_ok = trans_engine.audit_translation(source_clause, translated_ok, "hi")
    assert qa_ok.qa_status == "PASSED"

    # Dropped numbers triggers review
    translated_bad = "Yeh amendment Article 102 add karta hai."
    qa_bad = trans_engine.audit_translation(source_clause, translated_bad, "hi")
    assert qa_bad.qa_status == "REVIEW_REQUIRED"
    assert len(qa_bad.number_mismatches) > 0


def test_voice_direction_styles() -> None:
    vd = VoiceDirector()
    p1 = vd.select_style_for_text("Under Article 32, the Supreme Court protects citizens.")
    assert p1.style == DeliveryStyle.SERIOUS_CONSTITUTIONAL
    assert p1.pace_wpm <= 125.0

    p2 = vd.select_style_for_text("Constituent Assembly debates reveal the historical origin.")
    assert p2.style == DeliveryStyle.HISTORICAL_STORYTELLING

    p3 = vd.select_style_for_text("Namaste aur swagat hai UPSC Studio mein.")
    assert p3.style == DeliveryStyle.CURIOSITY_DISCOVERY


def test_audio_aware_subtitle_synchronization(tmp_path: Path) -> None:
    sync = AudioAwareSubtitleSynchronizer(tmp_path)
    sentences = [
        "Welcome to UPSC Studio.",
        "Today we explore Fundamental Rights in depth.",
        "Article 32 provides the constitutional remedy.",
    ]
    srt_out = tmp_path / "test.srt"
    vtt_out = tmp_path / "test.vtt"

    res = sync.generate_subtitles(sentences, total_audio_sec=9.0, out_srt=srt_out, out_vtt=vtt_out, lang_code="en")
    assert res["total_segments"] == 3
    assert srt_out.exists()
    assert vtt_out.exists()

    srt_content = srt_out.read_text(encoding="utf-8")
    assert "00:00:00,000 -->" in srt_content
    assert "Article 32" in srt_content

    vtt_content = vtt_out.read_text(encoding="utf-8")
    assert "WEBVTT" in vtt_content
    assert "00:00:00.000 -->" in vtt_content


def test_multilingual_tts_synthesis(tmp_path: Path) -> None:
    tts = MultilingualTTSEngine(tmp_path)
    wav_out = tmp_path / "output_test_en.wav"

    res = tts.synthesize_speech(
        text="The Supreme Court of India is the guarantor of Fundamental Rights.",
        lang_code="en",
        output_wav=wav_out,
    )
    assert wav_out.exists()
    assert wav_out.stat().st_size > 1000
    assert res["duration_sec"] > 1.0
    assert res["language"] == "en"


def test_youtube_dub_pack_builder_generates_all_assets(tmp_path: Path) -> None:
    builder = YouTubeDubPackBuilder(tmp_path)
    sections = [
        {
            "section_id": "SEC_01",
            "title": "Introduction",
            "narration": "Namaste aur swagat hai UPSC Studio mein.",
        },
        {
            "section_id": "SEC_02",
            "title": "Core Concept",
            "narration": "Sabse pehle basic meaning samajhte hain.",
        },
    ]

    # Test dub pack generation across Hindi, English, and Bengali
    res = builder.build_dub_pack(
        chapter_title="Fundamental Rights: Scope, Writs, and Judicial Review",
        canonical_script_segments=sections,
        target_languages=["hi", "en", "bn"],
    )

    pack_dir = Path(res["pack_dir"])
    assert (pack_dir / "README_UPLOAD_STEPS.md").exists()
    assert (pack_dir / "video_manifest.json").exists()

    for lang in ["hi", "en", "bn"]:
        lang_dir = pack_dir / lang
        assert lang_dir.exists()
        assert (lang_dir / "audio_track.wav").exists()
        assert (lang_dir / "subtitles.srt").exists()
        assert (lang_dir / "subtitles.vtt").exists()
        assert (lang_dir / "metadata.json").exists()
        assert (lang_dir / "translated_script.md").exists()
        assert (lang_dir / "qa_report.json").exists()

        meta = json.loads((lang_dir / "metadata.json").read_text(encoding="utf-8"))
        assert "localized_title" in meta
        assert "localized_description" in meta


def test_youtube_publisher_localized_metadata_and_captions(tmp_path: Path) -> None:
    yt = YouTubePublisher(token_path=tmp_path / "mock_token.json")

    # Localized metadata update requires oauth token
    res_loc = yt.update_localized_metadata("fake_id", {"hi": {"title": "शीर्षक", "description": "विवरण"}})
    assert res_loc["status"] == "PENDING_OAUTH_CONNECTION"

    # Caption upload requires oauth token
    srt = tmp_path / "dummy.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    res_cap = yt.upload_caption_track("fake_id", "hi", srt)
    assert res_cap["status"] == "PENDING_OAUTH_CONNECTION"
