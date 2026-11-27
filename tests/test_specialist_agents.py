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


def test_specialist_agents_execution_and_contracts(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "test_agents.db")
    proj_mgr = ProjectManager(conn, tmp_path / "projects")
    proj = proj_mgr.create_project(
        ProjectCreate(
            name="Specialist Test Project",
            chapter_title="Fundamental Rights: Scope and Writs",
            exam_cycle="2026",
            cutoff_date="2026-11-26",
            target_duration_min=5,
            tts_enabled=True,
        )
    )

    context = AgentExecutionContext(
        project_id=proj.id,
        project_dir=Path(proj.root_dir),
        run_id="run_spec_test",
        topic_title=proj.chapter_title,
        content_pillar="UPSC_CIVIL_SERVICES",
        cutoff_date=proj.cutoff_date,
        target_duration_min=5,
        tts_enabled=True,
        metadata={"conn": conn},
    )

    # 1. Executive Producer (AGENT_01)
    agent_01 = get_specialist_agent("AGENT_01")
    res_01 = agent_01.run(context)
    assert res_01.status == AgentStatus.COMPLETED
    assert "production_plan" in res_01.outputs
    context.upstream_outputs["AGENT_01"] = {"status": "COMPLETED", **res_01.outputs}

    # 2. Topic Researcher (AGENT_02)
    agent_02 = get_specialist_agent("AGENT_02")
    res_02 = agent_02.run(context)
    assert res_02.status == AgentStatus.COMPLETED
    assert "research_brief" in res_02.outputs
    assert len(res_02.outputs["research_brief"]["learning_objectives"]) >= 4
    context.upstream_outputs["AGENT_02"] = {"status": "COMPLETED", **res_02.outputs}

    # 3. Research Source Collector (AGENT_03)
    agent_03 = get_specialist_agent("AGENT_03")
    res_03 = agent_03.run(context)
    assert res_03.status == AgentStatus.COMPLETED
    assert res_03.outputs["sources_count"] >= 2
    context.upstream_outputs["AGENT_03"] = {"status": "COMPLETED", **res_03.outputs}

    # 4. Independent Fact Checker (AGENT_04)
    agent_04 = get_specialist_agent("AGENT_04")
    res_04 = agent_04.run(context)
    assert res_04.status == AgentStatus.COMPLETED
    assert res_04.outputs["claims_extracted_count"] >= 2
    context.upstream_outputs["AGENT_04"] = {"status": "COMPLETED", **res_04.outputs}

    # 5. Claim-to-Source Verifier (AGENT_05)
    agent_05 = get_specialist_agent("AGENT_05")
    res_05 = agent_05.run(context)
    assert res_05.status == AgentStatus.COMPLETED
    assert res_05.outputs["verified_claims"] >= 2
    context.upstream_outputs["AGENT_05"] = {"status": "COMPLETED", **res_05.outputs}

    # 6. Source Freshness Auditor (AGENT_06)
    agent_06 = get_specialist_agent("AGENT_06")
    res_06 = agent_06.run(context)
    assert res_06.status == AgentStatus.COMPLETED
    assert res_06.outputs["is_fresh"] is True
    context.upstream_outputs["AGENT_06"] = {"status": "COMPLETED", **res_06.outputs}

    # 7. Curriculum Mapper (AGENT_07)
    agent_07 = get_specialist_agent("AGENT_07")
    res_07 = agent_07.run(context)
    assert res_07.status == AgentStatus.COMPLETED
    assert "chapter_map" in res_07.outputs
    context.upstream_outputs["AGENT_07"] = {"status": "COMPLETED", **res_07.outputs}

    # 8. Topic Coverage Auditor (AGENT_08)
    agent_08 = get_specialist_agent("AGENT_08")
    res_08 = agent_08.run(context)
    assert res_08.status == AgentStatus.COMPLETED
    assert res_08.outputs["coverage_items_count"] > 0
    context.upstream_outputs["AGENT_08"] = {"status": "COMPLETED", **res_08.outputs}

    # 9. Instructional Designer (AGENT_09)
    agent_09 = get_specialist_agent("AGENT_09")
    res_09 = agent_09.run(context)
    assert res_09.status == AgentStatus.COMPLETED
    assert "pedagogical_plan" in res_09.outputs
    context.upstream_outputs["AGENT_09"] = {"status": "COMPLETED", **res_09.outputs}

    # 10. Teaching Script Writer (AGENT_10)
    agent_10 = get_specialist_agent("AGENT_10")
    res_10 = agent_10.run(context)
    assert res_10.status == AgentStatus.COMPLETED
    assert res_10.outputs["sections_count"] > 0
    context.upstream_outputs["AGENT_10"] = {"status": "COMPLETED", **res_10.outputs}

    # 11. Hinglish Language Editor (AGENT_11)
    agent_11 = get_specialist_agent("AGENT_11")
    res_11 = agent_11.run(context)
    assert res_11.status == AgentStatus.COMPLETED
    assert Path(res_11.outputs["display_script_path"]).exists()
    assert Path(res_11.outputs["spoken_script_path"]).exists()
    context.upstream_outputs["AGENT_11"] = {"status": "COMPLETED", **res_11.outputs}

    # 13. Visual Research Director (AGENT_13)
    context.upstream_outputs["AGENT_12"] = {"status": "COMPLETED"}
    agent_13 = get_specialist_agent("AGENT_13")
    res_13 = agent_13.run(context)
    assert res_13.status == AgentStatus.COMPLETED
    assert "visual_guidelines" in res_13.outputs
    context.upstream_outputs["AGENT_13"] = {"status": "COMPLETED", **res_13.outputs}

    # 14. Storyboard Architect (AGENT_14)
    agent_14 = get_specialist_agent("AGENT_14")
    res_14 = agent_14.run(context)
    assert res_14.status == AgentStatus.COMPLETED
    assert res_14.outputs["scenes_count"] > 0
    context.upstream_outputs["AGENT_14"] = {"status": "COMPLETED", **res_14.outputs}


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
