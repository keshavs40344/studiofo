"""Specialist Agents 07-12: Curriculum Mapping, Coverage Auditing, Pedagogy, Scriptwriting, Hinglish Editing, and Story Editing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from upsc_studio.academic.specialists import SpecialistProfileEngine
from upsc_studio.agents.contracts import (
    AgentExecutionContext,
    AgentExecutionResult,
    AgentRole,
    AgentStatus,
    QualityCheckStatus,
)
from upsc_studio.agents.specialists.base import BaseSpecialistAgent
from upsc_studio.publishing.editorial_optimizer import EditorialOptimizer
from upsc_studio.syllabus.engine import SyllabusEngine
from upsc_studio.teaching.engine import TeachingEngine
from upsc_studio.teaching.hinglish_director import HinglishDirector
from upsc_studio.universal.categories import CategoryRegistry
from upsc_studio.universal.completeness_auditor import TopicCompletenessAuditor
from upsc_studio.universal.knowledge_mapper import KnowledgeMapper
from upsc_studio.universal.pedagogy import UniversalPedagogyEngine


class CurriculumMapperAgent(BaseSpecialistAgent):
    """AGENT_07: Curriculum Mapper mapping topic to official syllabus requirements or knowledge taxonomy."""

    agent_id = "AGENT_07"
    role = AgentRole.CURRICULUM_MAPPER
    name = "Curriculum Mapper"
    description = "Maps chapter to official UPSC syllabus papers/subtopics or general science/knowledge taxonomies."
    dependencies = ["AGENT_02"]
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        conn = context.metadata.get("conn")
        syllabus_engine = SyllabusEngine(conn)
        chapter_map = syllabus_engine.map_chapter(
            project_id=context.project_id,
            project_dir=context.project_dir,
            chapter_title=context.topic_title,
        )

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED,
            quality_status=QualityCheckStatus.PASSED,
            outputs={"chapter_map": chapter_map},
            artifacts_created=[str(context.project_dir / "syllabus" / "syllabus_coverage.json")],
        )


class TopicCoverageAuditorAgent(BaseSpecialistAgent):
    """AGENT_08: Topic Coverage Auditor producing 16-point knowledge scope and coverage matrix."""

    agent_id = "AGENT_08"
    role = AgentRole.TOPIC_COVERAGE_AUDITOR
    name = "Topic Coverage Auditor"
    description = "Generates 16-point knowledge scope, Topic Coverage Matrix, and detects missing prerequisite concepts."
    dependencies = ["AGENT_06", "AGENT_07"]
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        km = KnowledgeMapper()
        topic_map = km.build_topic_map(
            topic_title=context.topic_title,
            target_duration_min=context.target_duration_min,
        )

        map_dict = topic_map.to_dict()
        out_path = context.project_dir / "research" / "topic_knowledge_map.json"
        out_path.write_text(json.dumps(map_dict, indent=2, ensure_ascii=False), encoding="utf-8")

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED,
            quality_status=QualityCheckStatus.PASSED,
            outputs={"topic_knowledge_map": map_dict, "coverage_items_count": len(topic_map.coverage_matrix)},
            artifacts_created=[str(out_path)],
        )


class InstructionalDesignerAgent(BaseSpecialistAgent):
    """AGENT_09: Instructional Designer planning 18-step pedagogical progression and duration schedule."""

    agent_id = "AGENT_09"
    role = AgentRole.INSTRUCTIONAL_DESIGNER
    name = "Instructional Designer"
    description = "Plans the 18-step pedagogical progression, section time budgets, learning tracks, and cognitive progression."
    dependencies = ["AGENT_08"]
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        pedagogy = UniversalPedagogyEngine()
        subcat = CategoryRegistry().detect_category(context.topic_title)
        subcat_id = subcat.subcategory_id if subcat else "GENERAL"

        steps = pedagogy.initialize_progression(context.topic_title, subcat_id)
        if "brain" in context.topic_title.lower() or "science" in context.topic_title.lower():
            pedagogy.mark_not_applicable(steps, 14, "Universal biological mechanisms operate independently of human legal jurisdiction.")

        ped_summary = pedagogy.validate_and_summarize(steps)
        out_path = context.project_dir / "teaching" / "pedagogical_plan.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(ped_summary, indent=2, ensure_ascii=False), encoding="utf-8")

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED,
            quality_status=QualityCheckStatus.PASSED,
            outputs={"pedagogical_plan": ped_summary},
            artifacts_created=[str(out_path)],
        )


class TeachingScriptWriterAgent(BaseSpecialistAgent):
    """AGENT_10: Teaching Script Writer authoring structured teaching script from verified claims."""

    agent_id = "AGENT_10"
    role = AgentRole.TEACHING_SCRIPT_WRITER
    name = "Teaching Script Writer"
    description = "Authors structured teaching script explaining mechanisms, examples, and analysis using verified claims."
    dependencies = ["AGENT_09"]
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        conn = context.metadata.get("conn")
        teaching_engine = TeachingEngine(conn, context.project_dir)

        upstream_map = context.upstream_outputs.get("AGENT_07", {}).get("chapter_map", {})
        pkg = teaching_engine.generate_teaching_package(
            project_id=context.project_id,
            chapter_title=context.topic_title,
            chapter_map=upstream_map,
            tts_enabled=context.tts_enabled,
            target_duration_min=context.target_duration_min,
        )

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED,
            quality_status=QualityCheckStatus.PASSED,
            outputs={"sections_count": len(pkg.get("sections", [])), "teaching_package": pkg},
            artifacts_created=[
                str(context.project_dir / "teaching" / "script_hinglish.md"),
                str(context.project_dir / "teaching" / "teaching_outline.md"),
            ],
        )


class HinglishLanguageEditorAgent(BaseSpecialistAgent):
    """AGENT_11: Hinglish Language Editor producing separate Display, Spoken TTS, and Subtitle tracks."""

    agent_id = "AGENT_11"
    role = AgentRole.HINGLISH_LANGUAGE_EDITOR
    name = "Hinglish Language Editor"
    description = "Translates/refines script into authentic Hinglish with Devanagari Hindi structure and standard English terms."
    dependencies = ["AGENT_10"]
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        conn = context.metadata.get("conn")
        claims_rows = conn.execute(
            "SELECT * FROM claims WHERE project_id = ? AND status = 'VERIFIED'",
            (context.project_id,),
        ).fetchall()
        verified_claims = [
            dict(r) for r in claims_rows
            if (r["verification_notes"] or "").startswith("HUMAN_ATTESTED_BY:")
            and "Evidence excerpt:" in (r["verification_notes"] or "")
            and len((r["verification_notes"] or "").split("Evidence excerpt:", 1)[1].strip()) >= 10
        ]
        if not verified_claims:
            return AgentExecutionResult(
                agent_id=self.agent_id, agent_role=self.role, status=AgentStatus.FAILED,
                quality_status=QualityCheckStatus.INSUFFICIENT_EVIDENCE,
                errors=["Hinglish editing is blocked because no human-attested factual claims are available."],
            )

        director = HinglishDirector(context.project_dir)
        pkg = director.export_documentary_package(
            chapter_title=context.topic_title,
            project_dir=context.project_dir,
            target_duration_min=context.target_duration_min,
            verified_claims=verified_claims,
        )

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED,
            quality_status=QualityCheckStatus.PASSED,
            outputs={
                "display_script_path": pkg.display_script_path,
                "spoken_script_path": pkg.tts_spoken_script_path,
                "subtitles_script_path": pkg.subtitles_script_path,
                "sections_count": len(pkg.sections),
            },
            artifacts_created=[pkg.display_script_path, pkg.tts_spoken_script_path, pkg.subtitles_script_path],
        )


class DocumentaryStoryEditorAgent(BaseSpecialistAgent):
    """AGENT_12: Documentary Story Editor polishing narrative arc, opening hooks, and shorts candidates."""

    agent_id = "AGENT_12"
    role = AgentRole.DOCUMENTARY_STORY_EDITOR
    name = "Documentary Story Editor"
    description = "Polishes documentary narrative arc, opening hooks, conceptual bridges, and YouTube Shorts candidates."
    dependencies = ["AGENT_11"]
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        from upsc_studio.db.schemas import SceneSpec
        sb_path = context.project_dir / "storyboard" / "storyboard.json"
        scenes = []
        if sb_path.exists():
            scenes = [SceneSpec(**s) for s in json.loads(sb_path.read_text(encoding="utf-8"))]

        optimizer = EditorialOptimizer()
        res = optimizer.optimize_and_extract_shorts(
            project_dir=context.project_dir,
            chapter_title=context.topic_title,
            primary_papers=["Mains GS"],
            scenes=scenes,
        )

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED,
            quality_status=QualityCheckStatus.PASSED,
            outputs={"editorial_summary": res},
            artifacts_created=[str(context.project_dir / "publishing" / "editorial_retention_plan.json")],
        )
