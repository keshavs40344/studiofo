"""Unit tests for all 24 UPSC Studio specialist agents."""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from upsc_studio.agents.contracts import (
    AgentExecutionContext,
    AgentRole,
    AgentStatus,
    QualityCheckStatus,
    SPECIALIST_REGISTRY,
)
from upsc_studio.agents.specialists.factory import get_specialist_agent, list_all_specialists
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate
from upsc_studio.projects.manager import ProjectManager


def test_specialist_registry_completeness() -> None:
    specialists = list_all_specialists()
    assert len(specialists) == 24, "Must implement exactly 24 specialist agents."
    
    roles = [s.role for s in specialists]
    assert len(set(roles)) == 24, "Every specialist agent must have a distinct unique role."

    # Verify each agent from SPECIALIST_REGISTRY maps to an instantiated agent
    for spec in SPECIALIST_REGISTRY:
        agent = get_specialist_agent(spec.agent_id)
        assert agent is not None, f"Agent '{spec.agent_id}' must be registered in factory."
        assert agent.role == spec.role
        assert agent.is_retry_safe == spec.is_retry_safe
        assert agent.has_side_effects == spec.has_side_effects


def test_source_collector_does_not_fabricate_sources_or_claims(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "test_agents.db")
    proj_mgr = ProjectManager(conn, tmp_path / "projects")
    proj = proj_mgr.create_project(
        ProjectCreate(
            name="Evidence Integrity Test",
            chapter_title="Fundamental Rights: Scope and Writs",
            exam_cycle="2026",
            cutoff_date="2026-11-26",
            target_duration_min=5,
            tts_enabled=False,
        )
    )
    context = AgentExecutionContext(
        project_id=proj.id,
        project_dir=Path(proj.root_dir),
        run_id="run_evidence_integrity",
        topic_title=proj.chapter_title,
        metadata={"conn": conn},
    )

    agent_01 = get_specialist_agent("AGENT_01")
    result_01 = agent_01.run(context)
    assert result_01.status == AgentStatus.COMPLETED
    context.upstream_outputs["AGENT_01"] = {"status": "COMPLETED", **result_01.outputs}

    agent_02 = get_specialist_agent("AGENT_02")
    result_02 = agent_02.run(context)
    assert result_02.status == AgentStatus.COMPLETED
    context.upstream_outputs["AGENT_02"] = {"status": "COMPLETED", **result_02.outputs}

    agent_03 = get_specialist_agent("AGENT_03")
    result_03 = agent_03.run(context)
    assert result_03.status == AgentStatus.FAILED
    assert result_03.quality_status == QualityCheckStatus.INSUFFICIENT_EVIDENCE
    assert "will not fabricate sources" in result_03.errors[0]
    assert conn.execute("SELECT count(*) FROM sources WHERE project_id = ?", (proj.id,)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM claims WHERE project_id = ?", (proj.id,)).fetchone()[0] == 0


def test_claim_verifier_requires_human_attestation(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "test_attestation.db")
    proj_mgr = ProjectManager(conn, tmp_path / "projects")
    proj = proj_mgr.create_project(
        ProjectCreate(
            name="Attestation Test",
            chapter_title="Article 32",
            exam_cycle="2026",
            cutoff_date="2026-11-26",
            target_duration_min=5,
            tts_enabled=False,
        )
    )
    from upsc_studio.research.verifier import EvidenceEngine

    engine = EvidenceEngine(conn, Path(proj.root_dir))
    source_id = engine.add_source(
        project_id=proj.id,
        title="Constitution of India",
        publisher="Government of India",
        source_tier="PRIMARY_OFFICIAL",
        pub_date="2024-01-01",
    )
    claim_id = engine.add_claim(
        project_id=proj.id,
        statement="Article 32 permits approaching the Supreme Court for enforcement of Part III rights.",
        chapter_section="Constitutional Remedies",
        source_id=source_id,
        page_or_section="Article 32",
    )
    context = AgentExecutionContext(
        project_id=proj.id,
        project_dir=Path(proj.root_dir),
        run_id="run_attestation",
        topic_title="Article 32",
        upstream_outputs={"AGENT_04": {"status": "COMPLETED"}},
        metadata={"conn": conn},
    )
    verifier = get_specialist_agent("AGENT_05")
    result = verifier.run(context)
    assert result.status == AgentStatus.FAILED
    assert result.quality_status == QualityCheckStatus.INSUFFICIENT_EVIDENCE
    row = conn.execute("SELECT status FROM claims WHERE id = ?", (claim_id,)).fetchone()
    assert row["status"] == "HUMAN_REVIEW_REQUIRED"

    engine.verify_claim_against_source(
        claim_id=claim_id,
        source_id=source_id,
        page_or_section="Article 32, Clause 1",
        evidence_excerpt="The right to move the Supreme Court by appropriate proceedings for enforcement of Part III rights.",
        reviewer_id="human-reviewer-1",
    )
    result = verifier.run(context)
    assert result.quality_status == QualityCheckStatus.PASSED
    row = conn.execute("SELECT status, verification_notes FROM claims WHERE id = ?", (claim_id,)).fetchone()
    assert row["status"] == "VERIFIED"
    assert row["verification_notes"].startswith("HUMAN_ATTESTED_BY:human-reviewer-1")


def test_attestation_requires_reviewer_and_matching_project(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "test_attestation_scope.db")
    proj_mgr = ProjectManager(conn, tmp_path / "projects")
    first = proj_mgr.create_project(ProjectCreate(name="Project One", chapter_title="Article 32"))
    second = proj_mgr.create_project(ProjectCreate(name="Project Two", chapter_title="Article 14"))
    from upsc_studio.research.verifier import EvidenceEngine

    engine = EvidenceEngine(conn, Path(first.root_dir))
    source_id = engine.add_source(first.id, "Constitution", "Government of India", "PRIMARY_OFFICIAL")
    claim_id = engine.add_claim(first.id, "Article 32 provides a constitutional remedy.", "Remedies")
    with pytest.raises(ValueError, match="reviewer_id"):
        engine.verify_claim_against_source(claim_id, source_id, "Article 32", "Sufficient excerpt text.")
    second_engine = EvidenceEngine(conn, Path(second.root_dir))
    second_source = second_engine.add_source(second.id, "Other source", "Publisher", "OTHER")
    with pytest.raises(ValueError, match="same project"):
        engine.verify_claim_against_source(claim_id, second_source, "Article 32", "Sufficient excerpt text.", reviewer_id="reviewer")


def test_specialist_agent_blocked_on_missing_upstream(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "test_block.db")
    context = AgentExecutionContext(
        project_id="p_block_test",
        project_dir=tmp_path,
        run_id="run_block_test",
        topic_title="Blocked Test Topic",
        upstream_outputs={},  # empty upstream
        metadata={"conn": conn},
    )

    # AGENT_04 depends on AGENT_03
    agent_04 = get_specialist_agent("AGENT_04")
    res = agent_04.run(context)
    assert res.status == AgentStatus.BLOCKED
    assert any("upstream dependency 'AGENT_03'" in err for err in res.errors)
