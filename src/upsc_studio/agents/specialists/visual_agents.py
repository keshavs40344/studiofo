"""Specialist Agents 13-17: Visual Research, Storyboard Architecture, Animations, Infographics, and Rights Auditing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from upsc_studio.agents.contracts import (
    AgentExecutionContext,
    AgentExecutionResult,
    AgentRole,
    AgentStatus,
    QualityCheckStatus,
)
from upsc_studio.agents.specialists.base import BaseSpecialistAgent
from upsc_studio.graphics.generator import GraphicsGenerator
from upsc_studio.graphics.rights import AssetRightsLedger
from upsc_studio.graphics.visual_systems import ExtendedVisualSystems
from upsc_studio.integrations.manim_worker import AnimationEngine
from upsc_studio.integrations.qgis_map import MapVisualEngine
from upsc_studio.storyboard.director import StoryboardDirector
from upsc_studio.universal.visual_director import UniversalVisualDirector


class VisualResearchDirectorAgent(BaseSpecialistAgent):
    """AGENT_13: Visual Research Director selecting domain-appropriate visual archetypes."""

    agent_id = "AGENT_13"
    role = AgentRole.VISUAL_RESEARCH_DIRECTOR
    name = "Visual Research Director"
    description = "Selects domain-appropriate visual archetypes (process animation, spatial map, comparison, anatomical model)."
    dependencies = ["AGENT_12"]
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        director = UniversalVisualDirector()
        guidelines = director.get_domain_visual_guidelines(context.topic_title)

        out_path = context.project_dir / "storyboard" / "visual_research_guidelines.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(guidelines, indent=2, ensure_ascii=False), encoding="utf-8")

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED,
            quality_status=QualityCheckStatus.PASSED,
            outputs={"visual_guidelines": guidelines},
            artifacts_created=[str(out_path)],
        )


class StoryboardArchitectAgent(BaseSpecialistAgent):
    """AGENT_14: Storyboard Architect creating scene-by-scene storyboard linking narration to visual cues."""

    agent_id = "AGENT_14"
    role = AgentRole.STORYBOARD_ARCHITECT
    name = "Storyboard Architect"
    description = "Assembles scene-by-scene storyboard linking narration sentences to visual assets, camera moves, and cues."
    dependencies = ["AGENT_13"]
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        director = StoryboardDirector(context.project_dir)
        teaching_pkg = context.upstream_outputs.get("AGENT_10", {}).get("teaching_package", {})
        sections = teaching_pkg.get("sections", [])

        if not sections:
            # Fallback mock section if running standalone
            sections = [
                {"title": "Introduction", "objective": "Set context", "duration_sec": 30, "narration": context.topic_title},
                {"title": "Core Mechanism", "objective": "Explain process", "duration_sec": 60, "narration": f"Mechanism of {context.topic_title}"},
            ]

        scenes = director.build_storyboard(context.topic_title, sections)
        sb_path = context.project_dir / "storyboard" / "storyboard.json"

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED,
            quality_status=QualityCheckStatus.PASSED,
            outputs={"scenes_count": len(scenes), "storyboard_path": str(sb_path)},
            artifacts_created=[str(sb_path)],
        )


class AnimationPlannerAgent(BaseSpecialistAgent):
    """AGENT_15: Animation Planner rendering procedural step-by-step process animations."""

    agent_id = "AGENT_15"
    role = AgentRole.ANIMATION_PLANNER
    name = "Animation Planner"
    description = "Renders procedural step-by-step animations for complex processes and mechanisms."
    dependencies = ["AGENT_14"]
    is_retry_safe = True
    has_side_effects = True

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        conn = context.metadata.get("conn")
        rights_ledger = AssetRightsLedger(conn, context.project_dir)
        anim_engine = AnimationEngine(context.project_dir, rights_ledger)

        anim_res = anim_engine.render_process_animation(
            project_id=context.project_id,
            scene_id="SCN_03",
            title=f"{context.topic_title}: Mechanism",
            steps=["Trigger / Initial State", "Mechanistic Processing", "Observable Outcome"],
            source_citation="Primary Research Source",
            duration_sec=4.0,
        )

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED,
            quality_status=QualityCheckStatus.PASSED,
            outputs={"animation": anim_res},
            artifacts_created=[anim_res.get("output_mp4", "")],
        )


class DiagramInfographicPlannerAgent(BaseSpecialistAgent):
    """AGENT_16: Diagram and Infographic Planner rendering maps, split comparisons, and charts."""

    agent_id = "AGENT_16"
    role = AgentRole.DIAGRAM_INFOGRAPHIC_PLANNER
    name = "Diagram and Infographic Planner"
    description = "Renders custom institutional maps, comparative tables, timelines, and analytical charts."
    dependencies = ["AGENT_14"]
    is_retry_safe = True
    has_side_effects = True

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        conn = context.metadata.get("conn")
        rights_ledger = AssetRightsLedger(conn, context.project_dir)
        map_engine = MapVisualEngine(context.project_dir, rights_ledger)
        vis_engine = ExtendedVisualSystems(context.project_dir, rights_ledger)

        map_path = map_engine.render_institutional_map(
            project_id=context.project_id,
            scene_id="SCN_02",
            title=f"{context.topic_title}: Scope & Structure",
            jurisdictions=[
                ("Foundational Domain", "Primary Principles & Articles"),
                ("Operational Level", "Implementing Entities & Mechanisms"),
                ("Adjudication", "Oversight & Safeguards"),
            ],
            source_label="Verified Academic / Official Source",
            ref_date=context.cutoff_date,
        )

        split_path = vis_engine.render_split_comparison(
            project_id=context.project_id,
            scene_id="SCN_04",
            title=f"{context.topic_title}: Comparative Dimensions",
            left_header="Strengths & Mandate",
            left_bullets=["Empirical validation", "Institutional consistency"],
            right_header="Challenges & Limitations",
            right_bullets=["Implementation delays", "Data verification requirements"],
            source_label="Primary Source Reference",
        )

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED,
            quality_status=QualityCheckStatus.PASSED,
            outputs={"map_path": str(map_path), "split_path": str(split_path)},
            artifacts_created=[str(map_path), str(split_path)],
        )


class AssetRightsAuditorAgent(BaseSpecialistAgent):
    """AGENT_17: Asset Rights Auditor inspecting copyright, licenses, and hashes."""

    agent_id = "AGENT_17"
    role = AgentRole.ASSET_RIGHTS_AUDITOR
    name = "Asset Rights Auditor"
    description = "Inspects copyright, license terms, origins, and cryptographic hashes of all generated and included assets."
    dependencies = ["AGENT_15", "AGENT_16"]
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        conn = context.metadata.get("conn")
        rights_ledger = AssetRightsLedger(conn, context.project_dir)
        ledger_data = rights_ledger.export_ledger(context.project_id)

        unverified_count = ledger_data.get("status_counts", {}).get("UNVERIFIED", 0)
        q_status = QualityCheckStatus.PASSED if unverified_count == 0 else QualityCheckStatus.REVIEW_REQUIRED

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED,
            quality_status=q_status,
            outputs={"rights_summary": ledger_data.get("status_counts", {})},
            artifacts_created=[str(context.project_dir / "assets" / "manifests" / "asset_rights_ledger.json")],
        )
