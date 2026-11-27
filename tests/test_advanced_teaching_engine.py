"""Comprehensive stress and acceptance tests for Advanced Documentary Teaching Engine."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, VerificationStatus
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.research.verifier import EvidenceEngine
from upsc_studio.teaching.concept_explainer import ConceptExplainerEngine, ExplanationCoverage
from upsc_studio.teaching.engine import TeachingEngine
from upsc_studio.teaching.study_pack import StudyPackBuilder
from upsc_studio.teaching.topic_map import ConceptCategory, ContentPillar, TopicConcept, TopicMapBuilder


def test_structured_topic_map_generation_and_components(tmp_path: Path) -> None:
    """Requirement 1: Verify structured topic map contains all 10 required components."""
    builder = TopicMapBuilder()
    topic_map = builder.build_topic_map(
        topic_title="Fundamental Rights and Judicial Review",
        content_category="upsc",
        verified_claims=[
            {"id": "clm_01", "statement": "Part III guarantees Fundamental Rights."},
            {"id": "clm_02", "statement": "Article 32 provides writ enforcement mechanism in Supreme Court."},
            {"id": "clm_03", "statement": "Maneka Gandhi (1978) established due process under Article 21."},
        ],
    )

    # 1. Learning objectives
    assert len(topic_map.learning_objectives) >= 4
    assert any("constitutional" in o.lower() for o in topic_map.learning_objectives)

    # 2. Prerequisite knowledge
    assert len(topic_map.prerequisite_knowledge) >= 2

    # 3. Required concepts & 4. Definitions
    assert len(topic_map.required_concepts) >= 4
    for c in topic_map.required_concepts:
        assert c.name
        assert c.definition
        # 5. Mechanisms
        assert len(c.mechanisms) > 0
        # 7. Causes & consequences
        assert len(c.causes_and_consequences) > 0
        # 8. Examples
        assert len(c.examples) > 0
        # 9. Counterexamples / limitations
        assert len(c.counterexamples_and_limitations) > 0
        # 10. Common misconceptions
        assert len(c.common_misconceptions) > 0
        assert "misconception" in c.common_misconceptions[0]
        assert "correction" in c.common_misconceptions[0]


def test_missing_concept_injection() -> None:
    """Requirement 7: Missing-concept injection must flag pedagogical incompleteness."""
    builder = TopicMapBuilder()
    topic_map = builder.build_topic_map("Photosynthesis", content_category="general_knowledge")

    # Invalidate by removing required concepts
    topic_map.required_concepts = []

    explainer = ConceptExplainerEngine()
    rep = explainer.map_and_validate_concepts(topic_map, [])

    assert rep.is_pedagogically_complete is False
    assert rep.total_required_concepts == 0


def test_incorrect_definition_injection() -> None:
    """Requirement 7: Injected empty/invalid definition must trigger incomplete explanation."""
    builder = TopicMapBuilder()
    topic_map = builder.build_topic_map("Urban Heat Islands", content_category="general_knowledge")

    # Inject empty definition into a required concept
    topic_map.required_concepts[0].definition = ""

    explainer = ConceptExplainerEngine()
    rep = explainer.map_and_validate_concepts(topic_map, [])

    assert rep.is_pedagogically_complete is False
    # Definition or mechanism issue flagged
    assert any("lacks" in issue.lower() or "unsupported" in issue.lower() for issue in rep.validation_issues)


def test_incomplete_explanation_detection() -> None:
    """Requirement 7: Shallow keyword-only passage without mechanism must be flagged INCOMPLETE."""
    builder = TopicMapBuilder()
    topic_map = builder.build_topic_map("Monetary Transmission Mechanism", content_category="general_knowledge")

    # Force a concept to have shallow explanation with no mechanism markers
    c_mech = topic_map.required_concepts[1]
    c_mech.category = ConceptCategory.MECHANISM
    c_mech.definition = "Just interest."
    c_mech.mechanisms = []  # No mechanism text

    explainer = ConceptExplainerEngine()
    rep = explainer.map_and_validate_concepts(topic_map, [])

    mech_exp = next(e for e in rep.explanations if e.concept_id == c_mech.concept_id)
    assert mech_exp.coverage_status in (ExplanationCoverage.INCOMPLETE, ExplanationCoverage.UNSUPPORTED)
    assert rep.is_pedagogically_complete is False


def test_incorrect_answer_detection_in_mcqs(tmp_path: Path) -> None:
    """Requirement 6 & 7: Practice questions must have verifiable answers and sound explanations."""
    builder = TopicMapBuilder()
    topic_map = builder.build_topic_map(
        "Fundamental Rights",
        content_category="upsc",
        verified_claims=[{"id": "clm_10", "statement": "Article 14 guarantees equality before law."}],
    )

    pack_builder = StudyPackBuilder(tmp_path)
    mcqs = pack_builder._build_practice_mcqs(topic_map, [{"id": "clm_10", "statement": "Article 14"}])

    assert len(mcqs) > 0
    for mcq in mcqs:
        assert mcq["correct_option"] in mcq["options"]
        assert len(mcq["options"]) == 4
        assert mcq["source_evidence_link"]
        assert "Statement 1 is correct" in mcq["explanation"]
        assert mcq["is_official_pyq"] is False  # Never claim practice items are official PYQs


def test_category_contamination_prevention(tmp_path: Path) -> None:
    """Requirement 5: GK and Deep Dive projects must NOT leak UPSC Prelims/Mains terminology."""
    conn = init_db(tmp_path / "gk_test.db")
    mgr = ProjectManager(conn, tmp_path / "projects")
    proj = mgr.create_project(
        ProjectCreate(name="Science Documentary", chapter_title="Plate Tectonics & Earthquakes")
    )
    proj_dir = Path(proj.root_dir)

    ev = EvidenceEngine(conn, proj_dir)
    src = ev.add_source(proj.id, "USGS Seismology", "USGS", "PRIMARY_OFFICIAL", url="https://usgs.gov")
    ev.add_claim(
        proj.id,
        "Lithospheric plates glide over the asthenosphere causing tectonic subduction.",
        "Mechanism",
        status=VerificationStatus.VERIFIED,
        source_id=src,
        page_or_section="Section 4.1 Plate Kinematics",
    )

    engine = TeachingEngine(conn, proj_dir)
    pkg = engine.generate_teaching_package(
        project_id=proj.id,
        chapter_title=proj.chapter_title,
        chapter_map={"primary_papers": ["Science & General Knowledge"]},
        content_category="general_knowledge",
    )

    assert pkg["content_category"] == "general_knowledge"

    # Verify no UPSC Prelims / Mains files leaked in GK mode
    assert not (proj_dir / "teaching" / "prelims_track.md").exists()
    assert (proj_dir / "teaching" / "topic_context.md").exists()

    notes_text = (proj_dir / "teaching" / "study_notes.md").read_text(encoding="utf-8")
    assert "GS Paper II" not in notes_text
    assert "Mains GS" not in notes_text
    assert "UPSC CSE" not in notes_text


def test_unsupported_claim_detection(tmp_path: Path) -> None:
    """Requirement 7: Unsupported/unverified claims must be flagged and isolated from teaching package."""
    conn = init_db(tmp_path / "unsup_test.db")
    mgr = ProjectManager(conn, tmp_path / "projects")
    proj = mgr.create_project(
        ProjectCreate(name="Unsupported Claim Project", chapter_title="Quantum Computing")
    )
    proj_dir = Path(proj.root_dir)

    ev = EvidenceEngine(conn, proj_dir)
    # Add an unverified claim
    ev.add_claim(
        proj.id,
        "Superposition was discovered in 2025 by a secret agency.",
        "Unverified",
        status=VerificationStatus.UNSUPPORTED,
    )

    engine = TeachingEngine(conn, proj_dir)
    pkg = engine.generate_teaching_package(
        project_id=proj.id,
        chapter_title=proj.chapter_title,
        chapter_map={"primary_papers": ["Science"]},
        content_category="general_knowledge",
    )

    assert pkg["content_readiness"] == "INSUFFICIENT_EVIDENCE"
    assert pkg["blocked_claims_excluded"] == 1
    assert pkg["verified_claims_used"] == 0

    script = (proj_dir / "teaching" / "script_hinglish.md").read_text(encoding="utf-8")
    assert "secret agency" not in script
    assert "Insufficient information" in script


def test_current_affairs_cutoff_enforcement() -> None:
    """Requirement 5: Current Affairs without explicit cutoff date must be rejected."""
    builder = TopicMapBuilder()
    with pytest.raises(ValueError, match="Current Affairs projects require an explicit cutoff_date"):
        builder.build_topic_map("Election Laws Amendment", content_category="current_affairs", cutoff_date=None)


def test_full_connected_study_pack_generation(tmp_path: Path) -> None:
    """Requirement 4: Verify generation of all 10 connected educational deliverables."""
    conn = init_db(tmp_path / "full_pack.db")
    mgr = ProjectManager(conn, tmp_path / "projects")
    proj = mgr.create_project(
        ProjectCreate(
            name="Federalism Pack",
            chapter_title="Constitutional Federalism in India",
            cutoff_date="2026-11-26",
        )
    )
    proj_dir = Path(proj.root_dir)

    ev = EvidenceEngine(conn, proj_dir)
    src = ev.add_source(proj.id, "Constitution of India", "Govt of India", "PRIMARY_OFFICIAL", url="https://legislative.gov.in")
    ev.add_claim(
        proj.id,
        "Article 1 declares India that is Bharat shall be a Union of States.",
        "Foundations",
        status=VerificationStatus.VERIFIED,
        source_id=src,
        page_or_section="Article 1",
    )
    ev.add_claim(
        proj.id,
        "Seventh Schedule establishes Union, State, and Concurrent legislative lists.",
        "Division of Powers",
        status=VerificationStatus.VERIFIED,
        source_id=src,
        page_or_section="Schedule 7",
    )

    engine = TeachingEngine(conn, proj_dir)
    pkg = engine.generate_teaching_package(
        project_id=proj.id,
        chapter_title=proj.chapter_title,
        chapter_map={"primary_papers": ["Mains GS Paper II"]},
        content_category="upsc",
    )

    assert "study_pack" in pkg
    t_dir = proj_dir / "teaching"

    # Verify all 10 deliverables are written and non-empty
    assert (t_dir / "structured_topic_map.json").stat().st_size > 0
    assert (t_dir / "script_hinglish.md").stat().st_size > 0
    assert (t_dir / "recording_script.md").stat().st_size > 0
    assert (t_dir / "study_notes.md").stat().st_size > 0
    assert (t_dir / "revision_sheet.md").stat().st_size > 0
    assert (t_dir / "revision_notes.md").stat().st_size > 0
    assert (t_dir / "glossary.json").stat().st_size > 0
    assert (t_dir / "definitions.md").stat().st_size > 0
    assert (t_dir / "concept_map.mermaid").stat().st_size > 0
    assert (t_dir / "definitions_and_mindmap.md").stat().st_size > 0
    assert (t_dir / "flashcards.json").stat().st_size > 0
    assert (t_dir / "practice_mcqs.json").stat().st_size > 0
    assert (t_dir / "question_bank.json").stat().st_size > 0
    assert (t_dir / "mains_answer_frameworks.md").stat().st_size > 0
    assert (t_dir / "chapter_summary.md").stat().st_size > 0
