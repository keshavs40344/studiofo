"""Tests for Phase 19: Universal Documentary Intelligence & Complete Topic Coverage Engine."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from upsc_studio.db.database import init_db
from upsc_studio.universal.categories import CategoryRegistry, ContentPillar, SubcategoryDefinition
from upsc_studio.universal.formats import DocumentaryFormatType, FormatSelector, FORMAT_REGISTRY
from upsc_studio.universal.pedagogy import UniversalPedagogyEngine, PedagogicalStatus
from upsc_studio.universal.knowledge_mapper import KnowledgeMapper, ExplanationStatus, ImportanceLevel
from upsc_studio.universal.visual_director import UniversalVisualDirector, VisualArchetype
from upsc_studio.universal.current_affairs_researcher import (
    CurrentAffairsResearchEngine,
    SourcePriorityTier,
    ClaimNature,
)
from upsc_studio.universal.completeness_auditor import TopicCompletenessAuditor
from upsc_studio.universal.duplicate_checker import DuplicateExplanationChecker


def test_category_registry_and_dynamic_extension(tmp_path: Path) -> None:
    reg = CategoryRegistry()

    # 1. Verify default 4 pillars
    all_cats = reg.list_all()
    assert len(all_cats) >= 12
    pillars = {c.pillar for c in all_cats}
    assert ContentPillar.UPSC_AND_CIVIL_SERVICES in pillars
    assert ContentPillar.GENERAL_KNOWLEDGE in pillars
    assert ContentPillar.CURRENT_AFFAIRS in pillars
    assert ContentPillar.DEEP_DIVE_DOCUMENTARY in pillars

    # 2. Verify dynamic addition of a new category without code changes
    new_sub = SubcategoryDefinition(
        subcategory_id="ASTRO_EXOPLANETS",
        pillar=ContentPillar.GENERAL_KNOWLEDGE,
        name="Exoplanetary Atmospheres and Biosignatures",
        description="Spectroscopic detection of biosignatures in habitable exoplanets.",
        default_visual_style="Spectroscopic Absorption Simulation",
        primary_source_types=["SCIENTIFIC_JOURNAL"],
        tags=["exoplanet", "james webb", "biosignature", "astrophysics"],
    )
    reg.register_subcategory(new_sub)
    retrieved = reg.get_subcategory("ASTRO_EXOPLANETS")
    assert retrieved is not None
    assert retrieved.name == "Exoplanetary Atmospheres and Biosignatures"

    # 3. Export to JSON and reload
    cfg_json = tmp_path / "custom_categories.json"
    reg.export_to_json(cfg_json)
    reg2 = CategoryRegistry(cfg_json)
    assert reg2.get_subcategory("ASTRO_EXOPLANETS") is not None


def test_documentary_formats_and_duration_validation() -> None:
    # 1. Verify 10 formats
    assert len(FORMAT_REGISTRY) == 10
    assert DocumentaryFormatType.COMPLETE_CHAPTER_DOCUMENTARY in FORMAT_REGISTRY
    assert DocumentaryFormatType.DEEP_DIVE_EXPLAINER in FORMAT_REGISTRY
    assert DocumentaryFormatType.CURRENT_AFFAIRS_ANALYSIS in FORMAT_REGISTRY
    assert DocumentaryFormatType.SCIENCE_TECH_EXPLAINER in FORMAT_REGISTRY
    assert DocumentaryFormatType.SHORT_DOCUMENTARY in FORMAT_REGISTRY
    assert DocumentaryFormatType.DOCUMENTARY_SERIES in FORMAT_REGISTRY

    # 2. Verify Short Documentary disclaimer
    short_fmt = FormatSelector.get_format(DocumentaryFormatType.SHORT_DOCUMENTARY)
    assert "must not be labelled as complete topic coverage" in short_fmt.disclaimer

    # 3. Verify validation against artificial compression
    valid, err = FormatSelector.validate_duration_for_topic(subtopic_count=14, target_duration_min=5)
    assert not valid
    assert "Minimum recommended duration is 15 minutes" in err

    valid_ok, err_ok = FormatSelector.validate_duration_for_topic(subtopic_count=14, target_duration_min=25)
    assert valid_ok
    assert err_ok is None


def test_18_step_pedagogy_progression_and_justification_rules() -> None:
    ped = UniversalPedagogyEngine()
    steps = ped.initialize_progression("How the Human Brain Processes Information")
    assert len(steps) == 18

    # Test Rule: Cannot mark NOT_APPLICABLE without a recorded reason
    with pytest.raises(ValueError, match="cannot be marked NOT_APPLICABLE without a recorded explanatory reason"):
        ped.mark_not_applicable(steps, 14, reason="")

    # Mark with valid reason
    step14 = ped.mark_not_applicable(
        steps, 14, reason="Biological sensory transduction is universal biological physics, not human legal history."
    )
    assert step14.status == PedagogicalStatus.NOT_APPLICABLE
    assert step14.not_applicable_reason != ""

    # Cover step 1
    ped.record_coverage(steps, 1, "The human brain is a biological organ comprising 86 billion neurons.", scene_id="SCN_01")
    assert steps[0].status == PedagogicalStatus.COVERED

    audit = ped.audit_pedagogical_completeness(steps)
    assert audit["covered_count"] == 1
    assert audit["not_applicable_count"] == 1
    assert not audit["is_pedagogically_complete"]


def test_visual_explanation_director_archetypes() -> None:
    vd = UniversalVisualDirector()

    # 1. Science/Brain
    brain_vis = vd.plan_visual_for_concept(
        scene_id="SCN_01",
        concept_title="Synaptic Action Potential",
        domain_category="GK_BRAIN_NEUROSCIENCE",
        narration_text="Action potentials trigger calcium influx causing vesicle exocytosis across the synaptic cleft.",
    )
    assert brain_vis.archetype == VisualArchetype.NEURAL_CELLULAR_PROCESS
    assert "synaptic" in brain_vis.visual_summary.lower()
    assert "misconception_prevented" in brain_vis.to_dict()

    # 2. Economy
    econ_vis = vd.plan_visual_for_concept(
        scene_id="SCN_02",
        concept_title="Monetary Policy Repo Rate",
        domain_category="UPSC_ECONOMY",
        narration_text="When RBI increases repo rate, borrowing costs rise, cooling aggregate demand.",
    )
    assert econ_vis.archetype == VisualArchetype.ECONOMIC_FLOW

    # 3. Current Affairs / Judiciary
    ca_vis = vd.plan_visual_for_concept(
        scene_id="SCN_03",
        concept_title="Supreme Court 9-Judge Bench Verdict",
        domain_category="CA_JUDICIARY_DEVELOPMENTS",
        narration_text="The 9-judge Constitution bench held that privacy is intrinsic under Article 21.",
    )
    assert ca_vis.archetype == VisualArchetype.CASE_LAW_LADDER
    assert "ratio decidendi" in ca_vis.conceptual_relationship.lower()


def test_current_affairs_research_engine() -> None:
    care = CurrentAffairsResearchEngine(cutoff_date="2026-11-26")

    # Test Rule: Never present a prediction as an established fact
    with pytest.raises(ValueError, match="Future prediction cannot be framed as established fact"):
        care.register_claim(
            claim_id="CLM_PRED_ERR",
            text="The Supreme Court has occurred established fact to overturn the law in 2027.",
            nature=ClaimNature.PREDICTION,
            source_title="Speculative Blog",
            source_tier=SourcePriorityTier.TIER_8_SECONDARY_ANALYSIS,
            source_url="https://example.com/spec",
            event_date="2027-01-01",
            publication_date="2026-11-20",
        )

    # Register valid confirmed fact with Primary Official source
    c1 = care.register_claim(
        claim_id="CLM_FACT_01",
        text="A 7-judge Constitution Bench of the Supreme Court held that sub-classification of SCs/STs is permissible.",
        nature=ClaimNature.CONFIRMED_FACT,
        source_title="Supreme Court Judgment — State of Punjab v. Davinder Singh",
        source_tier=SourcePriorityTier.TIER_3_JUDICIAL_VERDICT,
        source_url="https://main.sci.gov.in/judgment/davinder_singh_2024",
        event_date="2024-08-01",
        publication_date="2024-08-01",
    )
    assert c1.verified
    assert c1.source_tier == SourcePriorityTier.TIER_3_JUDICIAL_VERDICT

    # Register properly labelled prediction
    c2 = care.register_claim(
        claim_id="CLM_PRED_OK",
        text="Legal scholars anticipate that state governments may establish expert empirical commissions before enacting quotas.",
        nature=ClaimNature.PREDICTION,
        source_title="Constitutional Law Review 2026",
        source_tier=SourcePriorityTier.TIER_6_PEER_REVIEWED,
        source_url="https://example.com/clr2026",
        event_date="2026-12-01",
        publication_date="2026-10-15",
    )
    assert c2.claim_nature == ClaimNature.PREDICTION

    # Evaluate live research and test update alert detection
    rep = care.evaluate_live_research(
        topic_title="Sub-classification of Scheduled Castes in India",
        claims=[c1, c2],
        existing_doc_date="2023-01-01",  # Existing video from 2023
    )
    assert rep.confirmed_facts_count == 1
    assert rep.predictions_labelled_count == 1
    assert len(rep.update_alerts) > 0  # Flags update needed because event occurred in 2024


def test_topic_completeness_auditor_omission_detection() -> None:
    auditor = TopicCompletenessAuditor()
    km = KnowledgeMapper()

    # Topic Map for Brain processing
    brain_map = km.build_topic_map("How the Human Brain Processes Information")

    # 1. Incomplete script: deliberately omits synaptic transmission and neuroplasticity
    incomplete_script = (
        "The brain contains billions of neurons. Neurons have resting potential of -70 millivolts. "
        "When stimulated, action potentials propagate along axons. That is all."
    )
    rep_incomplete = auditor.audit_completeness(
        knowledge_map=brain_map,
        script_text=incomplete_script,
        storyboard_scenes=[{"scene_id": "SCN_01", "title": "Neuron Structure"}],
        rendered_scene_ids=["SCN_01"],
    )
    assert not rep_incomplete.is_approved
    assert rep_incomplete.missing_items > 0
    assert len(rep_incomplete.critical_omissions) > 0
    assert any("HIGH IMPORTANCE OMISSION" in o for o in rep_incomplete.critical_omissions)

    # 2. Comprehensive script covering all coverage matrix concepts
    full_script = (
        "The human brain is a biological organ comprising 86 billion neurons. "
        "Each neuron maintains a resting potential of -70mV via the sodium-potassium ATPase pump defined as ion balance. "
        "Depolarization triggers an electrochemical action potential that jumps across nodes of Ranvier as a process of saltatory conduction. "
        "At the synaptic cleft, calcium influx causes vesicle exocytosis, releasing neurotransmitters like glutamate and GABA across the 20nm gap for example. "
        "The thalamus routes sensory inputs to the primary sensory cortex, operating as a Bayesian predictive machine because it minimizes prediction errors. "
        "Learning occurs through Long-Term Potentiation (LTP) and synaptic plasticity, activating NMDA receptors to strengthen synaptic connections. "
        "Finally, debunking neurological myths such as the 10 percent brain myth and hemisphere dichotomy, connecting modern applications to Brain-Computer Interfaces."
    )
    mock_scenes = [
        {"scene_id": "SCN_01", "title": "Neuron Structure & Resting Potential"},
        {"scene_id": "SCN_02", "title": "Action Potential & Saltatory Conduction"},
        {"scene_id": "SCN_03", "title": "Synaptic Transmission & Neurochemical Coding"},
        {"scene_id": "SCN_04", "title": "Thalamocortical Relay & Predictive Perception"},
        {"scene_id": "SCN_05", "title": "Memory Consolidation & Synaptic Plasticity"},
        {"scene_id": "SCN_06", "title": "Debunking Neurological Myths & Modern Applications"},
    ]
    rep_full = auditor.audit_completeness(
        knowledge_map=brain_map,
        script_text=full_script,
        storyboard_scenes=mock_scenes,
        rendered_scene_ids=[s["scene_id"] for s in mock_scenes],
    )
    assert rep_full.is_approved
    assert rep_full.actual_coverage_percentage >= 80.0
    assert len(rep_full.critical_omissions) == 0


def test_duplicate_explanation_checker(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "test_dup.db")
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)

    # Seed an existing project
    proj_dir = projects_dir / "existing_fr_proj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    teaching_dir = proj_dir / "teaching"
    teaching_dir.mkdir(parents=True, exist_ok=True)
    (teaching_dir / "script_hinglish_display.md").write_text(
        "Fundamental Rights Part III Articles 12 to 35. Article 12 defines State, Article 13 provides judicial review. "
        "Five writs are Habeas Corpus, Mandamus, Prohibition, Certiorari, Quo-Warranto.",
        encoding="utf-8",
    )
    conn.execute(
        "INSERT INTO projects (id, name, slug, chapter_title, exam_cycle, cutoff_date, root_dir, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("p_exist_1", "FR Master", "fr-master", "Fundamental Rights and Writs", "2026", "2026-11-26", str(proj_dir), "2026-01-01", "2026-01-01"),
    )
    conn.commit()

    checker = DuplicateExplanationChecker(conn, projects_dir)

    # 1. Test near-duplicate topic
    overlap_res = checker.check_topic_overlap(
        new_topic_title="Fundamental Rights and Writs in Indian Constitution",
        planned_subtopics=["Article 12 State", "Article 13 Judicial Review", "Five Writs Habeas Corpus Mandamus"],
    )
    assert overlap_res.is_duplicate
    assert overlap_res.recommended_action == "UPGRADE_EXISTING_VIDEO_DELTA"

    # 2. Test novel, non-overlapping topic
    novel_res = checker.check_topic_overlap(
        new_topic_title="How the Human Brain Processes Information and Synaptic LTP",
        planned_subtopics=["Action Potential", "Synaptic Cleft", "Long-Term Potentiation", "Thalamocortical Relay"],
    )
    assert not novel_res.is_duplicate
    assert novel_res.recommended_action == "PROCEED_NEW_DOCUMENTARY"
