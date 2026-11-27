"""Evidence-safety regression tests for teaching output and release research gates."""
from __future__ import annotations

from pathlib import Path

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, VerificationStatus
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.qa.auditor import QAAuditor
from upsc_studio.qa.ten_gates import TenGateAuditor
from upsc_studio.research.verifier import EvidenceEngine
from upsc_studio.syllabus.engine import SyllabusEngine
from upsc_studio.teaching.engine import TeachingEngine


def test_teaching_script_does_not_turn_unverified_notes_into_facts(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "evidence.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(name="Evidence safety", chapter_title="Urban Heat Islands")
    )
    project_dir = Path(project.root_dir)

    notes = (
        "A user note claims that a particular city adopted a policy in 2019. "
        "It also claims that a named committee recommended a specific reform."
    )
    package = TeachingEngine(conn, project_dir).generate_teaching_package(
        project_id=project.id,
        chapter_title=project.chapter_title,
        chapter_map={"primary_papers": ["Mains GS Paper III"]},
        notes_excerpt=notes,
        target_duration_min=10,
    )
    script = (project_dir / "teaching" / "script_hinglish.md").read_text(encoding="utf-8")
    qbank = (project_dir / "teaching" / "question_bank.json").read_text(encoding="utf-8")

    assert package["content_readiness"] == "INSUFFICIENT_EVIDENCE"
    assert "Insufficient information" in script
    assert "adopted a policy in 2019" not in script
    assert "named committee" not in script
    assert "Constituent Assembly" not in script
    assert "Ambedkar" not in script
    assert "Law Commission" not in script
    assert '"prelims_practice_mcqs": []' in qbank


def test_teaching_script_uses_only_verified_claim_text_and_external_source_gate(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "verified.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(name="Verified topic", chapter_title="Urban Heat Islands")
    )
    project_dir = Path(project.root_dir)
    evidence = EvidenceEngine(conn, project_dir)

    source_id = evidence.add_source(
        project.id,
        title="Official urban climate report",
        publisher="Government Research Agency",
        source_tier="PRIMARY_OFFICIAL",
        url="https://example.gov/reports/urban-climate",
    )
    claim_text = "The report identifies reduced urban vegetation as one contributing factor."
    evidence.add_claim(
        project.id,
        claim_text,
        "Drivers",
        status=VerificationStatus.VERIFIED,
        source_id=source_id,
        page_or_section="Chapter 2",
    )

    package = TeachingEngine(conn, project_dir).generate_teaching_package(
        project_id=project.id,
        chapter_title=project.chapter_title,
        chapter_map={"primary_papers": ["Mains GS Paper III"]},
        notes_excerpt="This additional note is not independently verified.",
        target_duration_min=10,
    )
    script = (project_dir / "teaching" / "script_hinglish.md").read_text(encoding="utf-8")

    assert package["content_readiness"] == "READY_FOR_HUMAN_REVIEW"
    assert claim_text in script
    assert "This additional note is not independently verified." not in script
    assert "Ambedkar" not in script

    qa = QAAuditor(conn, project_dir).run_all_checks(project.id)
    assert qa["academic"]["status"] == "PASSED"


def test_user_notes_are_not_counted_as_external_research_or_complete_syllabus(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "gates.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(name="Research gate", chapter_title="Federalism")
    )
    project_dir = Path(project.root_dir)
    evidence = EvidenceEngine(conn, project_dir)
    note_source = evidence.add_source(
        project.id,
        title="User supplied notes",
        publisher="Project User",
        source_tier="USER_NOTES",
    )
    evidence.add_claim(
        project.id,
        "Federalism distributes powers across levels of government.",
        "Definition",
        status=VerificationStatus.VERIFIED,
        source_id=note_source,
    )
    SyllabusEngine(conn).map_chapter(
        project_id=project.id,
        project_dir=project_dir,
        chapter_title=project.chapter_title,
        notes_text="",
    )

    qa = QAAuditor(conn, project_dir).run_all_checks(project.id)
    assert qa["academic"]["status"] == "FAILED"
    assert any("external source URL" in item for item in qa["academic"]["blocking_issues"])

    gates = TenGateAuditor(conn, project_dir).run_ten_gates(
        project.id, scenes=[], final_mp4=None,
    )
    assert gates["gates"]["B_RESEARCH_SOURCE"] == "FAILED"
    assert gates["gates"]["A_SYLLABUS_COMPLETENESS"] == "PENDING"
    assert gates["ready_for_publication"] == "PENDING"
