"""Tests for Phase 19: Hinglish-First UPSC Documentary Studio, Complete Knowledge Graph, Catalogue, and Gap Auditor."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import pytest

from upsc_studio.db.database import init_db
from upsc_studio.syllabus.knowledge_graph import KnowledgeGraph, UPSCStage, TopicDepth
from upsc_studio.syllabus.knowledge_catalogue import KnowledgeCatalogue, CatalogueStatus
from upsc_studio.publishing.channel_gap_auditor import ChannelGapAuditor, ChannelVideoItem, GapStatus
from upsc_studio.teaching.hinglish_director import HinglishDirector, ENGLISH_TECHNICAL_TERMS_PHONETIC
from upsc_studio.qa.documentary_quality_gate import DocumentaryQualityGate


def test_knowledge_graph_structure_and_hierarchy() -> None:
    kg = KnowledgeGraph()
    breakdown = kg.get_coverage_breakdown()

    # 1. Verify coverage across papers
    assert "Mains GS Paper II" in breakdown["by_paper"]
    assert "Prelims GS Paper I" in breakdown["by_paper"]
    assert "Prelims CSAT Paper II" in breakdown["by_paper"]
    assert "Mains GS Paper I" in breakdown["by_paper"]
    assert "Mains GS Paper III" in breakdown["by_paper"]
    assert "Mains GS Paper IV" in breakdown["by_paper"]
    assert "Mains Essay" in breakdown["by_paper"]

    # 2. Verify all 14 Fundamental Rights microtopics
    fr_node_ids = [
        "POL_FR_01_PHIL",
        "POL_FR_02_HIST",
        "POL_FR_03_ART12_13",
        "POL_FR_04_EQUALITY",
        "POL_FR_05_FREEDOM",
        "POL_FR_06_EXPLOITATION",
        "POL_FR_07_RELIGION",
        "POL_FR_08_CULTURE_EDU",
        "POL_FR_09_REMEDIES_ART32",
        "POL_FR_10_WRITS",
        "POL_FR_11_RESTRICTIONS_33_35",
        "POL_FR_12_JUDGMENTS",
        "POL_FR_13_DEBATES",
        "POL_FR_14_PYQ_MAINS",
    ]
    for nid in fr_node_ids:
        node = kg.get_node(nid)
        assert node is not None, f"Node {nid} must exist in knowledge graph."
        assert node.major_topic == "Fundamental Rights"
        assert node.stage == UPSCStage.MAINS

    # 3. Verify prerequisite dependencies
    prereqs_writs = kg.get_prerequisites("POL_FR_10_WRITS")
    assert any(p.node_id == "POL_FR_09_REMEDIES_ART32" for p in prereqs_writs)

    # 4. Verify learning path topological sort
    path = kg.get_learning_path("POL_FR_10_WRITS")
    path_ids = [n.node_id for n in path]
    assert "POL_FR_01_PHIL" in path_ids
    assert "POL_FR_09_REMEDIES_ART32" in path_ids
    assert path_ids.index("POL_FR_01_PHIL") < path_ids.index("POL_FR_09_REMEDIES_ART32")
    assert path_ids.index("POL_FR_09_REMEDIES_ART32") < path_ids.index("POL_FR_10_WRITS")

    # 5. Verify topic playlist
    playlist = kg.get_topic_playlist("Fundamental Rights")
    assert len(playlist) == 14
    pl_ids = [n.node_id for n in playlist]
    assert pl_ids[0] == "POL_FR_01_PHIL"


def test_knowledge_catalogue_lifecycle_and_invariants(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "test_catalogue.db")
    kg = KnowledgeGraph()
    cat = KnowledgeCatalogue(conn, kg)

    summary = cat.get_catalogue_summary()
    assert summary["total_entries"] == len(kg.nodes)
    assert summary["topics_published"] == 0

    # Test Invariant 1: Cannot mark PUBLISHED without a verified URL
    with pytest.raises(ValueError, match="cannot be marked PUBLISHED without a verified URL"):
        cat.update_status(
            node_id="POL_FR_01_PHIL",
            new_status=CatalogueStatus.PUBLISHED,
            published_video_url=None,
        )

    # With valid URL, publication succeeds
    updated = cat.update_status(
        node_id="POL_FR_01_PHIL",
        new_status=CatalogueStatus.PUBLISHED,
        published_video_url="https://www.youtube.com/watch?v=mock_fr01_vid",
    )
    assert updated.status == CatalogueStatus.PUBLISHED
    assert updated.published_video_url == "https://www.youtube.com/watch?v=mock_fr01_vid"

    # Test Invariant 2: Cannot mark QA_PASSED without passing QA gates
    with pytest.raises(ValueError, match="All academic, visual, audio, subtitle, and technical gates must pass"):
        cat.update_status(
            node_id="POL_FR_02_HIST",
            new_status=CatalogueStatus.QA_PASSED,
            qa_passed=False,
        )

    # When QA passes, transition succeeds
    updated_qa = cat.update_status(
        node_id="POL_FR_02_HIST",
        new_status=CatalogueStatus.QA_PASSED,
        qa_passed=True,
        qa_report_id="qa_rep_12345",
    )
    assert updated_qa.status == CatalogueStatus.QA_PASSED
    assert updated_qa.qa_report_id == "qa_rep_12345"

    summary_after = cat.get_catalogue_summary()
    assert summary_after["topics_published"] == 1
    assert summary_after["topics_qa_passed"] == 2  # PUBLISHED + QA_PASSED


def test_channel_gap_auditor() -> None:
    kg = KnowledgeGraph()
    auditor = ChannelGapAuditor(kg)

    mock_videos = [
        ChannelVideoItem(
            video_id="vid_fr_01",
            title="Fundamental Rights Philosophy and Justiciability in Constitution Part III",
            description="Complete analysis of fundamental rights philosophy, negative obligations and Magna Carta.",
            published_date="2026-02-15",
            transcript="fundamental rights negative obligations part iii justiciable constitutional philosophy",
            duration_sec=720,
        ),
        ChannelVideoItem(
            video_id="vid_outdated",
            title="Right to Equality and Reservation Policies in India",
            description="Articles 14 to 18 explained.",
            published_date="2020-01-10",  # >= 4 years old
            transcript="article 14 article 15 article 16 reasonable classification indira sawhney",
            duration_sec=600,
        ),
        ChannelVideoItem(
            video_id="vid_short",
            title="Writ Jurisdiction in Constitution of India",
            description="Short summary of writs.",
            published_date="2026-03-01",
            transcript="habeas corpus mandamus prohibition certiorari quo-warranto",
            duration_sec=120,  # < 3 minutes
        ),
    ]

    report = auditor.audit_channel_videos(
        channel_url="https://www.youtube.com/@UPSCStudioDemo",
        videos=mock_videos,
        reference_year=2026,
    )

    assert report.total_videos_scanned == 3
    assert report.total_syllabus_topics == len(kg.nodes)
    assert report.fully_covered_count >= 1

    # Check that outdated video was flagged as OUTDATED_FACTS
    outdated_res = next((r for r in report.topic_results if r.matched_video_id == "vid_outdated"), None)
    assert outdated_res is not None
    assert outdated_res.gap_status == GapStatus.OUTDATED_FACTS

    # Check that short video was flagged as INCOMPLETE_COVERAGE
    short_res = next((r for r in report.topic_results if r.matched_video_id == "vid_short"), None)
    assert short_res is not None
    assert short_res.gap_status == GapStatus.INCOMPLETE_COVERAGE

    # Verify upgrade plan contains recommendations
    assert len(report.upgrade_plan) > 0
    assert any(plan["action"] == "CREATE_NEW_VIDEO" for plan in report.upgrade_plan)
    assert any(plan["action"] == "UPGRADE_EXISTING_VIDEO" for plan in report.upgrade_plan)


def test_hinglish_director_multi_track_generation(tmp_path: Path) -> None:
    director = HinglishDirector(tmp_path)
    pkg = director.export_documentary_package(
        chapter_title="Fundamental Rights: Scope, Writs, and Judicial Review",
        project_dir=tmp_path,
        target_duration_min=15,
    )

    # 1. Verify 13 dimensions
    assert len(pkg.sections) == 13
    dims = [s.dimension_tag for s in pkg.sections]
    for required_dim in director.DIMENSIONS:
        assert required_dim in dims, f"Dimension {required_dim} must be covered."

    # 2. Verify all 3 track files exist
    disp_file = Path(pkg.display_script_path)
    spoken_file = Path(pkg.tts_spoken_script_path)
    sub_file = Path(pkg.subtitles_script_path)
    assert disp_file.exists()
    assert spoken_file.exists()
    assert sub_file.exists()

    disp_text = disp_file.read_text(encoding="utf-8")
    spoken_text = spoken_file.read_text(encoding="utf-8")
    sub_text = sub_file.read_text(encoding="utf-8")

    # 3. Verify Display script preserves natural Devanagari Hindi + standard English technical terms
    assert "Fundamental Rights" in disp_text
    assert "State" in disp_text
    assert "Article 21" in disp_text
    assert "Supreme Court" in disp_text
    assert "Habeas Corpus" in disp_text
    assert "मनमाने तरीके से नहीं कर सकती" in disp_text

    # 4. Verify TTS spoken script normalized code-switching into phonetic forms
    assert "फंडामेंटल राइट्स" in spoken_text
    assert "सुप्रीम कोर्ट" in spoken_text
    assert "हेबियस कॉर्पस" in spoken_text

    # 5. Verify Subtitle format (SRT numbering and timestamps)
    assert "00:00:00,000 -->" in sub_text
    assert "Fundamental Rights" in sub_text

    # 6. Verify pronunciation audit passed
    assert pkg.pronunciation_report["integrity_check"].startswith("PASSED")
    assert pkg.pronunciation_report["code_switch_instances"] > 10


def test_documentary_quality_gate(tmp_path: Path) -> None:
    gate = DocumentaryQualityGate()

    # Create dummy dummy files for audio, video, subtitle
    vid_file = tmp_path / "final_video.mp4"
    vid_file.write_bytes(b"dummy_mp4_bytes")
    aud_file = tmp_path / "audio.wav"
    aud_file.write_bytes(b"dummy_wav_bytes")
    sub_file = tmp_path / "subs.srt"
    sub_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nTest\n", encoding="utf-8")

    # 1. Complete verified project should PASS
    rep_pass = gate.evaluate_project(
        project_id="proj_pass_1",
        project_dir=tmp_path,
        chapter_title="Fundamental Rights: Nature and Scope",
        verified_claims_count=6,
        unverified_claims_count=0,
        rendered_video_path=vid_file,
        rendered_audio_path=aud_file,
        subtitles_path=sub_file,
        script_sections_count=13,
        pyq_count=3,
    )
    assert rep_pass.gate_status == "PASSED"
    assert rep_pass.overall_score >= 80.0
    assert len(rep_pass.hard_blockers) == 0
    assert len(rep_pass.dimension_scores) == 12

    # 2. Project with unverified claims should FAIL with hard blocker
    rep_fail_claims = gate.evaluate_project(
        project_id="proj_fail_1",
        project_dir=tmp_path,
        chapter_title="Unverified Topic",
        verified_claims_count=2,
        unverified_claims_count=3,  # unverified claims present
        rendered_video_path=vid_file,
        rendered_audio_path=aud_file,
        subtitles_path=sub_file,
        script_sections_count=13,
        pyq_count=3,
    )
    assert rep_fail_claims.gate_status == "FAILED"
    assert any("Critical factual error" in b for b in rep_fail_claims.hard_blockers)

    # 3. Project with missing/empty video file should FAIL
    empty_vid = tmp_path / "empty_video.mp4"
    empty_vid.write_bytes(b"")  # 0 bytes
    rep_fail_video = gate.evaluate_project(
        project_id="proj_fail_2",
        project_dir=tmp_path,
        chapter_title="Failed Render Topic",
        verified_claims_count=4,
        unverified_claims_count=0,
        rendered_video_path=empty_vid,
        rendered_audio_path=aud_file,
        subtitles_path=sub_file,
        script_sections_count=13,
        pyq_count=3,
    )
    assert rep_fail_video.gate_status == "FAILED"
    assert any("Failed video rendering" in b for b in rep_fail_video.hard_blockers)
