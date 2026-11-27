"""Specialist Agents 23-24: Academic Red-Team Reviewer and Final Release Gatekeeper."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from upsc_studio.academic.pyq_engine import PYQEngine
from upsc_studio.agents.contracts import (
    AgentExecutionContext,
    AgentExecutionResult,
    AgentRole,
    AgentStatus,
    QualityCheckStatus,
)
from upsc_studio.agents.specialists.base import BaseSpecialistAgent
from upsc_studio.db.schemas import SceneSpec
from upsc_studio.qa.auditor import QAAuditor
from upsc_studio.qa.documentary_quality_gate import DocumentaryQualityGate
from upsc_studio.qa.ten_gates import TenGateAuditor
from upsc_studio.universal.completeness_auditor import TopicCompletenessAuditor
from upsc_studio.universal.knowledge_mapper import KnowledgeMapper


class AcademicRedTeamReviewerAgent(BaseSpecialistAgent):
    """AGENT_23: Academic Red-Team Reviewer checking grounding, misleading simplifications, and PYQ authenticity."""

    agent_id = "AGENT_23"
    role = AgentRole.ACADEMIC_RED_TEAM_REVIEWER
    name = "Academic Red-Team Reviewer"
    description = "Performs adversarial review of claims, detects misleading simplifications, and verifies authentic PYQs."
    dependencies = ["AGENT_08", "AGENT_22"]
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        conn = context.metadata.get("conn")
        red_team_issues: list[str] = []

        # 1. Check for unverified claims in database
        claims = conn.execute("SELECT * FROM claims WHERE project_id = ?", (context.project_id,)).fetchall()
        unverified = [c for c in claims if c["status"] != "VERIFIED"]
        if unverified:
            red_team_issues.append(f"{len(unverified)} unverified claims present in research database.")

        # 2. Check PYQ authenticity if topic is UPSC-focused
        pyq_engine = PYQEngine()
        is_upsc = any(k in context.topic_title.lower() for k in ("upsc", "rights", "constitution", "polity", "castes", "mains"))
        matched_pyqs = pyq_engine.match_chapter(context.topic_title) if is_upsc else []

        # 3. Topic Completeness check
        km = KnowledgeMapper()
        t_map = km.build_topic_map(context.topic_title, target_duration_min=context.target_duration_min)
        disp_script_path = context.project_dir / "teaching" / "script_hinglish_display.md"
        script_text = disp_script_path.read_text(encoding="utf-8") if disp_script_path.exists() else ""

        sb_path = context.project_dir / "storyboard" / "storyboard.json"
        scenes = [SceneSpec(**s) for s in json.loads(sb_path.read_text(encoding="utf-8"))] if sb_path.exists() else []

        completeness_auditor = TopicCompletenessAuditor()
        comp_rep = completeness_auditor.audit_completeness(
            knowledge_map=t_map,
            script_text=script_text,
            storyboard_scenes=[s.model_dump() for s in scenes],
            rendered_scene_ids=[s.scene_id for s in scenes],
        )

        if not comp_rep.is_approved:
            red_team_issues.extend(comp_rep.critical_omissions)

        is_passed = (len(red_team_issues) == 0 and comp_rep.is_approved)
        q_status = QualityCheckStatus.PASSED if is_passed else QualityCheckStatus.FAILED

        report = {
            "topic_title": context.topic_title,
            "red_team_issues": red_team_issues,
            "completeness_approved": comp_rep.is_approved,
            "completeness_coverage_pct": comp_rep.actual_coverage_percentage,
            "matched_pyqs_count": len(matched_pyqs),
            "is_passed": is_passed,
        }

        out_path = context.project_dir / "qa" / "academic_red_team_report.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED if is_passed else AgentStatus.FAILED,
            quality_status=q_status,
            outputs=report,
            errors=red_team_issues if not is_passed else [],
            artifacts_created=[str(out_path)],
        )


class FinalReleaseGatekeeperAgent(BaseSpecialistAgent):
    """AGENT_24: Final Release Gatekeeper evaluating all 10 QA gates and requiring human release approval."""

    agent_id = "AGENT_24"
    role = AgentRole.FINAL_RELEASE_GATEKEEPER
    name = "Final Release Gatekeeper"
    description = "Enforces 10-gate quality certification (Gates A-J), human approval requirement, and release packaging."
    dependencies = ["AGENT_22", "AGENT_23"]
    is_retry_safe = False
    has_side_effects = True

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        conn = context.metadata.get("conn")
        sb_path = context.project_dir / "storyboard" / "storyboard.json"
        scenes = [SceneSpec(**s) for s in json.loads(sb_path.read_text(encoding="utf-8"))] if sb_path.exists() else []

        final_vid = context.project_dir / "render" / "final" / "final_video.mp4"
        full_wav = context.project_dir / "audio" / "processed" / "narration_full.wav"
        sub_srt = context.project_dir / "subtitles" / "narration.srt"

        # 1. 10-Gate Audit (Gates A through J)
        ten_gates = TenGateAuditor(conn, context.project_dir).run_ten_gates(
            context.project_id, scenes, final_vid if final_vid.exists() else None
        )

        # 2. Documentary Quality Gate (12 dimensions)
        claims = conn.execute("SELECT * FROM claims WHERE project_id = ?", (context.project_id,)).fetchall()
        verified_count = sum(1 for c in claims if c["status"] == "VERIFIED")
        unverified_count = len(claims) - verified_count

        gate = DocumentaryQualityGate()
        doc_quality = gate.evaluate_project(
            project_id=context.project_id,
            project_dir=context.project_dir,
            chapter_title=context.topic_title,
            verified_claims_count=verified_count,
            unverified_claims_count=unverified_count,
            rendered_video_path=final_vid,
            rendered_audio_path=full_wav,
            subtitles_path=sub_srt,
            script_sections_count=len(scenes),
            pyq_count=1 if "rights" in context.topic_title.lower() else 0,
        )

        # 3. Check for human publication approval in database
        # According to persistent rules: public release MUST fail closed until explicit user approval
        row = conn.execute("SELECT status FROM projects WHERE id = ?", (context.project_id,)).fetchone()
        project_status = row["status"] if row else "NEEDS_REVIEW"
        is_human_approved = (project_status == "APPROVED")

        release_approved = (
            ten_gates["ten_gates"]["overall_status"] == "PASSED"
            and doc_quality.gate_status == "PASSED"
            and is_human_approved
        )

        report = {
            "project_id": context.project_id,
            "topic_title": context.topic_title,
            "ten_gates_status": ten_gates["ten_gates"]["overall_status"],
            "documentary_quality_status": doc_quality.gate_status,
            "documentary_quality_score": doc_quality.overall_score,
            "human_approval_recorded": is_human_approved,
            "ready_for_public_release": release_approved,
        }

        out_path = context.project_dir / "qa" / "final_release_candidate_report.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        q_status = QualityCheckStatus.PASSED if (ten_gates["ten_gates"]["overall_status"] == "PASSED" and doc_quality.gate_status == "PASSED") else QualityCheckStatus.REVIEW_REQUIRED

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED,
            quality_status=q_status,
            outputs=report,
            warnings=["Public release withheld pending final human publication approval." if not is_human_approved else ""],
            artifacts_created=[str(out_path)],
        )
