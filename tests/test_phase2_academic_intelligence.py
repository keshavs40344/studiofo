"""Tests for Phase 2: Subject specialists, PYQ engine, Mains frameworks, section-wise voice, and 10 Golden Benchmarks."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from upsc_studio.academic.mains_analyzer import MainsAnswerAnalyzer
from upsc_studio.academic.pyq_engine import PYQEngine
from upsc_studio.academic.specialists import SpecialistProfileEngine
from upsc_studio.audio.section_voice import SectionVoiceManager
from upsc_studio.db.database import init_db
from upsc_studio.qa.benchmark_auditor import BenchmarkAuditor


def _write_wav(path: Path, dur: float = 1.5) -> None:
    sr = 44100
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        buf = bytearray()
        for i in range(int(sr * dur)):
            buf.extend(struct.pack("<h", int(10000 * math.sin(2.0 * math.pi * 220.0 * (i / sr)))))
        wf.writeframes(bytes(buf))


def test_subject_specialists_and_pyq_authenticity() -> None:
    spec = SpecialistProfileEngine()
    assert len(spec.profiles) == 8
    k_csat, _ = spec.select_profile("CSAT Data Interpretation", ["Prelims CSAT Paper II"])
    assert k_csat == "PRELIMS_CSAT"
    k_eth, _ = spec.select_profile("Ethics and Conflict of Interest", ["Mains GS Paper IV"])
    assert k_eth == "GS-IV"

    pyq = PYQEngine()
    matches = pyq.match_chapter("Anti-Defection Law and Tenth Schedule", ["PRE_GS1_POL"])
    assert any(m["year"] == 2022 and m["authenticity_status"] == "VERIFIED_OFFICIAL" for m in matches)

    bad_qbank = {"prelims_practice_mcqs": [{"id": "Q1", "label": "UPSC_PYQ"}]}
    assert len(pyq.validate_question_bank_authenticity(bad_qbank)) == 1


def test_mains_directive_analyzer() -> None:
    analyzer = MainsAnswerAnalyzer()
    spec = SpecialistProfileEngine()
    _, gs2 = spec.select_profile("Federalism", ["Mains GS Paper II"])
    fw = analyzer.build_framework("Critically examine cooperative federalism in India.", "Federalism", gs2)
    assert fw["directive_word"] == "CRITICALLY EXAMINE"
    assert fw["label"] == "EDUCATIONAL_EXAMPLE_NOT_OFFICIAL_UPSC_ANSWER"
    assert "Limitations & Criticisms" in fw["body_structure"]


def test_section_wise_voice_missing_and_retake_stitch(tmp_path: Path) -> None:
    mgr = SectionVoiceManager(tmp_path)
    sections = [
        {"section_id": "SEC_01", "narration": "Namaste aur swagat hai."},
        {"section_id": "SEC_02", "narration": "Aaj hum Federalism padhenge."},
    ]
    w1 = tmp_path / "s1.wav"
    w2 = tmp_path / "s2.wav"
    _write_wav(w1, 1.5)
    _write_wav(w2, 1.5)

    mgr.submit_section_audio("SEC_01", w1)
    rep1 = mgr.audit_and_stitch("proj_test", sections)
    assert rep1["all_sections_present"] is False
    assert rep1["missing_sections"] == ["SEC_02"]

    # Supply SEC_02 (or retake) -> stitches into narration_clean.wav
    mgr.submit_section_audio("SEC_02", w2)
    rep2 = mgr.audit_and_stitch("proj_test", sections)
    assert rep2["all_sections_present"] is True
    assert Path(rep2["stitched_narration"]).exists()


def test_golden_10_chapter_benchmarks(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "bench.db")
    auditor = BenchmarkAuditor(conn, tmp_path / "projects")
    report = auditor.run_all_benchmarks()
    assert report["total_benchmarks"] == 10
    assert report["check_counts"]["FAILED"] == 0
    assert report["check_counts"]["PASSED"] >= 30
    assert report["check_counts"]["HUMAN_REVIEW_REQUIRED"] >= 20
