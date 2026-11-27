"""Tests for Universal Knowledge and Documentary Intelligence specialists.

Verifies:
1. 6-domain classification and keyword weighting.
2. Domain specialist profiles and fact-checking rules.
3. 5-phase pedagogical outline generation.
4. Seamless integration with StagedChapterPipeline for non-UPSC content categories.
"""

from __future__ import annotations

import json
from pathlib import Path

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate
from upsc_studio.pipeline.staged import StagedChapterPipeline
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.universal.domain_engine import (
    DOMAIN_PROFILES,
    UniversalDomain,
    UniversalKnowledgeEngine,
)


def test_domain_detection_across_all_domains() -> None:
    """Verify domain detection across all 6 universal knowledge domains."""
    engine = UniversalKnowledgeEngine()

    # 1. Science & Tech
    d1 = engine.detect_domain("James Webb Space Telescope & Quantum Infrared Signals", "deep_dive")
    assert d1 == UniversalDomain.SCIENCE_AND_TECH

    # 2. History & World Affairs
    d2 = engine.detect_domain("Treaty of Versailles and the Outbreak of World War II", "general_knowledge")
    assert d2 == UniversalDomain.HISTORY_AND_WORLD

    # 3. Geography & Earth Systems
    d3 = engine.detect_domain("Indian Ocean Dipole and Monsoon Tectonic Pressures", "general_knowledge")
    assert d3 == UniversalDomain.GEOGRAPHY_AND_EARTH

    # 4. Economy & Industry
    d4 = engine.detect_domain("RBI Repo Rate Transmission, Inflation and Liquidity", "current_affairs")
    assert d4 == UniversalDomain.ECONOMY_AND_INDUSTRY

    # 5. Constitution & Law
    d5 = engine.detect_domain("Judicial Review and the Basic Structure Doctrine", "general_knowledge")
    assert d5 == UniversalDomain.CONSTITUTION_AND_LAW

    # 6. Philosophy & Thought
    d6 = engine.detect_domain("Utilitarianism vs Deontological Moral Philosophy", "deep_dive")
    assert d6 == UniversalDomain.PHILOSOPHY_AND_THOUGHT


def test_domain_specialist_profiles_contain_required_attributes() -> None:
    """Verify each domain has rich focus areas, pedagogical arc, and fact-checking standards."""
    engine = UniversalKnowledgeEngine()

    for domain in UniversalDomain:
        profile = DOMAIN_PROFILES[domain]
        assert len(profile.focus_areas) >= 4
        assert len(profile.pedagogical_arc) == 5
        assert len(profile.recommended_visuals) >= 3
        assert len(profile.common_misconceptions) >= 2
        assert len(profile.fact_checking_hierarchy) > 20
        assert len(profile.preferred_tone) > 5

    # Select domain profile dictionary
    key, profile_data = engine.select_domain_profile("Superconductors and Fusion Energy", "deep_dive")
    assert key == "SCIENCE_AND_TECH_SPECIALIST"
    assert profile_data["domain"] == "SCIENCE_AND_TECH"
    assert profile_data["content_category"] == "deep_dive"
    assert profile_data["source_review_required"] is True


def test_pedagogical_outline_generation() -> None:
    """Verify 5-phase educational outline adhering to the domain pedagogical arc."""
    engine = UniversalKnowledgeEngine()

    outline = engine.generate_pedagogical_outline(
        domain=UniversalDomain.GEOGRAPHY_AND_EARTH,
        chapter_title="Plate Tectonics and Deep Sea Trenches",
        target_duration_min=30,
    )

    assert len(outline) == 5
    # Durations should sum to target duration (30 min = 1800 sec)
    total_sec = sum(sec["target_duration_sec"] for sec in outline)
    assert total_sec == 1800

    # Phase 1: Physical Basis (15% = 270s)
    assert outline[0]["target_duration_sec"] == 270
    assert "Physical Basis" in outline[0]["pedagogical_role"]

    # Phase 2: Mechanism (35% = 630s)
    assert outline[1]["target_duration_sec"] == 630
    assert "Dynamic Process" in outline[1]["pedagogical_role"]

    # All sections must have learning objectives and visual categories
    for sec in outline:
        assert len(sec["learning_objective"]) > 10
        assert sec["visual_category"] in DOMAIN_PROFILES[UniversalDomain.GEOGRAPHY_AND_EARTH].recommended_visuals


def test_staged_pipeline_uses_universal_specialist_for_non_upsc_projects(tmp_path: Path) -> None:
    """Verify StagedChapterPipeline._stage_teaching adopts universal domain specialists for non-UPSC content."""
    conn = init_db(tmp_path / "universal.db")
    projects_root = tmp_path / "projects"
    manager = ProjectManager(conn, projects_root)

    # Create a Deep Dive Science project
    project = manager.create_project(
        ProjectCreate(
            name="Quantum Computing Deep Dive",
            chapter_title="Quantum Supremacy and Qubit Superposition",
            content_category="deep_dive",
        )
    )

    pipeline = StagedChapterPipeline(conn, projects_root)
    paths = pipeline._paths(Path(project.root_dir))

    # Provide initial dummy notes
    paths["notes"].parent.mkdir(parents=True, exist_ok=True)
    paths["notes"].write_text(
        "# Quantum Supremacy\n# Qubits and Decoherence\nNotes exploring quantum algorithmic speedup.",
        encoding="utf-8",
    )

    chapter_map = {
        "primary_papers": [],
        "mapped_items": [],
        "topic_headings": ["Quantum Supremacy", "Qubits and Decoherence"],
    }

    teaching_res = pipeline._stage_teaching(project.id, Path(project.root_dir), paths, chapter_map)

    assert teaching_res["status"] == "COMPLETED"
    assert teaching_res["specialist_profile"] == "SCIENCE_AND_TECH_SPECIALIST"
    assert teaching_res["matched_pyqs"] == 0

    # Verify persisted stage artifact
    saved_stage = json.loads(paths["teaching"].read_text(encoding="utf-8"))
    assert saved_stage["specialist_key"] == "SCIENCE_AND_TECH_SPECIALIST"
    assert saved_stage["specialist_profile"]["domain"] == "SCIENCE_AND_TECH"
    assert len(saved_stage["specialist_profile"]["pedagogical_arc"]) == 5
