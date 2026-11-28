"""Regression tests for Phase 16: duration planning tolerance, fact verification, task graph, TTS, and QA."""

from __future__ import annotations

from pathlib import Path
import pytest

from upsc_studio.agents.contracts import AGENT_REGISTRY, AgentStatus
from upsc_studio.agents.supervisor import ExecutiveProducer
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, VerificationStatus
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.publishing.youtube_publisher import YouTubePublisher
from upsc_studio.research.verifier import EvidenceEngine
from upsc_studio.teaching.duration_planner import DurationPlanner
from upsc_studio.teaching.engine import TeachingEngine
from upsc_studio.tts.adapter import PiperTTSEngine


def test_duration_planner_under_duration(tmp_path: Path) -> None:
    planner = DurationPlanner(words_per_minute=130.0)
    # Target 8 minutes (480s), but provided sections only total ~60s (under 70% threshold)
    sections = [
        {"section_id": "SEC_1", "title": "Intro", "narration": "Namaste dosto.", "duration_sec": 30.0},
        {"section_id": "SEC_2", "title": "Summary", "narration": "Yeh recap hai.", "duration_sec": 30.0},
    ]
    sched = planner.build_schedule(tmp_path, sections, target_duration_min=8)
    assert sched["status"] == "INSUFFICIENT_DURATION"
    assert sched["planned_duration_sec"] == 60.0
    assert sched["target_duration_sec"] == 480.0


def test_duration_planner_correct_duration(tmp_path: Path) -> None:
    planner = DurationPlanner(words_per_minute=130.0)
    # Target 5 minutes (300s), sections total 280s (fits between 0.80x and 1.15x)
    sections = [
        {"section_id": f"SEC_{i}", "title": f"Part {i}", "narration": "Short script sentence.", "duration_sec": 70.0}
        for i in range(1, 5)
    ]
    sched = planner.build_schedule(tmp_path, sections, target_duration_min=5)
    assert sched["status"] == "FITS_TARGET_DURATION"
    assert sched["planned_duration_sec"] == 280.0
    assert len(sched["multi_part_proposal"]) == 0


def test_duration_planner_over_duration_and_multi_part(tmp_path: Path) -> None:
    planner = DurationPlanner(words_per_minute=130.0)
    # Target 5 minutes (300s), sections total 450s (> 1.15x)
    sections = [
        {"section_id": f"SEC_{i}", "title": f"Deep Section {i}", "narration": "Detailed explanation.", "duration_sec": 150.0}
        for i in range(1, 4)
    ]
    sched = planner.build_schedule(tmp_path, sections, target_duration_min=5)
    assert sched["status"] == "MULTI_PART_RECOMMENDED"
    assert len(sched["multi_part_proposal"]) == 2
    assert sched["multi_part_proposal"][0]["part"] == 1
    assert sched["multi_part_proposal"][1]["part"] == 2


def test_duration_planner_actual_rendered_mismatch(tmp_path: Path) -> None:
    planner = DurationPlanner(words_per_minute=130.0)
    sections = [
        {"section_id": "SEC_1", "title": "Section", "narration": "Sentence text.", "duration_sec": 280.0}
    ]
    # Planned 280s for 5m target, but actual rendered audio was only 60s
    sched = planner.build_schedule(tmp_path, sections, target_duration_min=5, actual_rendered_sec=60.0)
    assert sched["rendered_mismatch"] is True
    assert sched["actual_rendered_duration_sec"] == 60.0


def test_teaching_engine_syllabus_preserving_expansion(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "teach.db")
    mgr = ProjectManager(conn, tmp_path / "projects")
    proj = mgr.create_project(
        ProjectCreate(
            name="Teaching Expansion Demo",
            chapter_title="Directive Principles of State Policy",
            target_duration_min=8,
        )
    )
    proj_dir = Path(proj.root_dir)
    engine = TeachingEngine(conn, proj_dir)

    # The lesson structure stays evidence-led; target duration never injects unsourced history.
    pkg = engine.generate_teaching_package(
        project_id=proj.id,
        chapter_title=proj.chapter_title,
        chapter_map={"primary_papers": ["GS-II"]},
        target_duration_min=8,
    )
    assert pkg["sections_count"] == 5
    assert pkg["content_readiness"] == "INSUFFICIENT_EVIDENCE"
    section_ids = [s["section_id"] for s in pkg["sections"]]
    assert section_ids == ["SEC_01", "SEC_02", "SEC_03", "SEC_04", "SEC_05"]
    script = (proj_dir / "teaching" / "script_hinglish.md").read_text(encoding="utf-8")
    assert "Constituent Assembly" not in script
    assert "Insufficient information" in script


def test_fact_verification_rejects_missing_page_or_source(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "fact.db")
    mgr = ProjectManager(conn, tmp_path / "projects")
    proj = mgr.create_project(ProjectCreate(name="Fact Test", chapter_title="Life & Liberty"))
    ev = EvidenceEngine(conn, tmp_path)

    # 1. Reject VERIFIED without source
    with pytest.raises(ValueError, match="source_id"):
        ev.add_claim(
            proj.id,
            "Article 21 guarantees right to life.",
            "Foundations",
            status=VerificationStatus.VERIFIED,
            source_id=None,
        )

    # 2. Reject VERIFIED with source but empty page/section reference
    src_id = ev.add_source(proj.id, "Constitution of India", "Govt", "PRIMARY_OFFICIAL")
    with pytest.raises(ValueError, match="page_or_section"):
        ev.add_claim(
            proj.id,
            "Article 21 guarantees right to life.",
            "Foundations",
            status=VerificationStatus.VERIFIED,
            source_id=src_id,
            page_or_section="",
        )


def test_fact_verification_conflict_detection(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "conflict.db")
    mgr = ProjectManager(conn, tmp_path / "projects")
    proj = mgr.create_project(ProjectCreate(name="Conflict Test", chapter_title="Committees"))
    ev = EvidenceEngine(conn, tmp_path)
    src_id = ev.add_source(proj.id, "Official Report", "Govt", "PRIMARY_OFFICIAL")

    ev.add_claim(
        proj.id,
        "Report established committee in 2018.",
        "Section 1",
        status=VerificationStatus.CONFLICTING,
        source_id=src_id,
        page_or_section="Page 5",
        verification_notes="Conflicting with official gazette notification",
    )
    conflicts = ev.detect_conflicts(proj.id)
    assert len(conflicts) >= 1
    assert "Conflicting" in conflicts[0]["reason"]


def test_task_graph_dependency_and_status(tmp_path: Path) -> None:
    assert len(AGENT_REGISTRY) == 24
    # Ensure all dependencies point to valid agent IDs
    all_ids = {a["id"] for a in AGENT_REGISTRY}
    for agent in AGENT_REGISTRY:
        for dep in agent["dependencies"]:
            assert dep in all_ids, f"Dependency {dep} in {agent['id']} is invalid"


def test_tts_voice_detection(tmp_path: Path) -> None:
    tts = PiperTTSEngine(tmp_path)
    caps = tts.detect_voice_capabilities()
    assert "piper_hindi_available" in caps
    assert "sapi_hindi_available" in caps
    assert "can_synthesize_hindi" in caps


def test_youtube_publisher_safety_requires_approval(tmp_path: Path) -> None:
    yt = YouTubePublisher(token_path=tmp_path / "mock_token.json")
    mp4 = tmp_path / "video.mp4"
    mp4.write_bytes(b"data")

    # Public upload without explicit human approval is blocked
    with pytest.raises(PermissionError, match="human_approved_by"):
        yt.upload_video(mp4, {"video_title": "Test"}, qa_passed=True, privacy_status="public", human_approved_by=None)
