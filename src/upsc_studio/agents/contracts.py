"""Multi-agent contracts, typed interfaces, and task graph specifications for UPSC Studio."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    EXECUTIVE_PRODUCER = "EXECUTIVE_PRODUCER"
    TOPIC_RESEARCHER = "TOPIC_RESEARCHER"
    RESEARCH_SOURCE_COLLECTOR = "RESEARCH_SOURCE_COLLECTOR"
    INDEPENDENT_FACT_CHECKER = "INDEPENDENT_FACT_CHECKER"
    CLAIM_TO_SOURCE_VERIFIER = "CLAIM_TO_SOURCE_VERIFIER"
    SOURCE_FRESHNESS_AUDITOR = "SOURCE_FRESHNESS_AUDITOR"
    CURRICULUM_MAPPER = "CURRICULUM_MAPPER"
    TOPIC_COVERAGE_AUDITOR = "TOPIC_COVERAGE_AUDITOR"
    INSTRUCTIONAL_DESIGNER = "INSTRUCTIONAL_DESIGNER"
    TEACHING_SCRIPT_WRITER = "TEACHING_SCRIPT_WRITER"
    HINGLISH_LANGUAGE_EDITOR = "HINGLISH_LANGUAGE_EDITOR"
    DOCUMENTARY_STORY_EDITOR = "DOCUMENTARY_STORY_EDITOR"
    VISUAL_RESEARCH_DIRECTOR = "VISUAL_RESEARCH_DIRECTOR"
    STORYBOARD_ARCHITECT = "STORYBOARD_ARCHITECT"
    ANIMATION_PLANNER = "ANIMATION_PLANNER"
    DIAGRAM_INFOGRAPHIC_PLANNER = "DIAGRAM_INFOGRAPHIC_PLANNER"
    ASSET_RIGHTS_AUDITOR = "ASSET_RIGHTS_AUDITOR"
    NARRATION_DIRECTOR = "NARRATION_DIRECTOR"
    PRONUNCIATION_AUDITOR = "PRONUNCIATION_AUDITOR"
    AUDIO_QUALITY_AUDITOR = "AUDIO_QUALITY_AUDITOR"
    SUBTITLE_TRANSLATION_AGENT = "SUBTITLE_TRANSLATION_AGENT"
    VIDEO_QUALITY_AUDITOR = "VIDEO_QUALITY_AUDITOR"
    ACADEMIC_RED_TEAM_REVIEWER = "ACADEMIC_RED_TEAM_REVIEWER"
    FINAL_RELEASE_GATEKEEPER = "FINAL_RELEASE_GATEKEEPER"


class AgentStatus(str, Enum):
    REGISTERED = "REGISTERED"
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    PAUSED = "PAUSED"
    SKIPPED = "SKIPPED"
    RECOVERY_REVIEW_REQUIRED = "RECOVERY_REVIEW_REQUIRED"


class QualityCheckStatus(str, Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class AgentExecutionContext(BaseModel):
    """Context passed to each specialist agent during task execution."""
    project_id: str
    project_dir: Path
    run_id: str
    topic_title: str
    content_pillar: str = "UPSC_CIVIL_SERVICES"
    cutoff_date: str = "2026-11-26"
    target_duration_min: int = 15
    tts_enabled: bool = True
    upstream_outputs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


class AgentTaskResult(BaseModel):
    task_id: str
    agent_id: str
    agent_name: str = ""
    status: AgentStatus = AgentStatus.REGISTERED
    dependencies: list[str] = Field(default_factory=list)
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)
    execution_time_sec: float = 0.0
    errors: list[str] = Field(default_factory=list)
    retry_count: int = 0
    verification_status: str = "PENDING"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentExecutionResult(BaseModel):
    """Standardized output returned by every specialist agent."""
    agent_id: str
    agent_role: AgentRole
    status: AgentStatus
    quality_status: QualityCheckStatus = QualityCheckStatus.PENDING
    execution_time_sec: float = 0.0
    outputs: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    artifacts_created: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTaskSpec(BaseModel):
    """Specification defining an agent's identity, dependencies, and execution rules in the DAG."""
    agent_id: str
    role: AgentRole
    name: str
    description: str
    dependencies: list[str] = Field(default_factory=list)
    is_retry_safe: bool = True
    has_side_effects: bool = False
    max_retries: int = 2


# 24 Specialist Production Agents in dependency order
SPECIALIST_REGISTRY: list[AgentTaskSpec] = [
    AgentTaskSpec(
        agent_id="AGENT_01",
        role=AgentRole.EXECUTIVE_PRODUCER,
        name="Executive Producer",
        description="Supervises production DAG, validates preconditions, orchestrates checkpoints, and manages recovery.",
        dependencies=[],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_02",
        role=AgentRole.TOPIC_RESEARCHER,
        name="Topic Researcher",
        description="Defines topic boundaries, primary research questions, learning outcomes, and foundational scope.",
        dependencies=["AGENT_01"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_03",
        role=AgentRole.RESEARCH_SOURCE_COLLECTOR,
        name="Research Source Collector",
        description="Identifies, gathers, and catalogues authoritative primary sources, acts, court judgments, and academic texts.",
        dependencies=["AGENT_02"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_04",
        role=AgentRole.INDEPENDENT_FACT_CHECKER,
        name="Independent Fact Checker",
        description="Extracts atomic claims, separates facts from interpretations/predictions, and checks for contradictions.",
        dependencies=["AGENT_03"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_05",
        role=AgentRole.CLAIM_TO_SOURCE_VERIFIER,
        name="Claim-to-Source Verifier",
        description="Performs substantive claim-to-source support review; marks unsupported claims as INSUFFICIENT_EVIDENCE.",
        dependencies=["AGENT_04"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_06",
        role=AgentRole.SOURCE_FRESHNESS_AUDITOR,
        name="Source Freshness Auditor",
        description="Audits source publication dates against cutoff date; flags obsolete legal provisions or outdated statistics.",
        dependencies=["AGENT_05"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_07",
        role=AgentRole.CURRICULUM_MAPPER,
        name="Curriculum Mapper",
        description="Maps chapter to official UPSC syllabus papers/subtopics or general science/knowledge taxonomies.",
        dependencies=["AGENT_02"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_08",
        role=AgentRole.TOPIC_COVERAGE_AUDITOR,
        name="Topic Coverage Auditor",
        description="Generates 16-point knowledge scope, Topic Coverage Matrix, and detects missing prerequisite concepts.",
        dependencies=["AGENT_06", "AGENT_07"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_09",
        role=AgentRole.INSTRUCTIONAL_DESIGNER,
        name="Instructional Designer",
        description="Plans the 18-step pedagogical progression, section time budgets, learning tracks, and cognitive progression.",
        dependencies=["AGENT_08"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_10",
        role=AgentRole.TEACHING_SCRIPT_WRITER,
        name="Teaching Script Writer",
        description="Authors structured teaching script explaining mechanisms, examples, and analysis using verified claims.",
        dependencies=["AGENT_09"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_11",
        role=AgentRole.HINGLISH_LANGUAGE_EDITOR,
        name="Hinglish Language Editor",
        description="Translates/refines script into authentic Hinglish with Devanagari Hindi structure and standard English terms.",
        dependencies=["AGENT_10"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_12",
        role=AgentRole.DOCUMENTARY_STORY_EDITOR,
        name="Documentary Story Editor",
        description="Polishes documentary narrative arc, opening hooks, conceptual bridges, and YouTube Shorts candidates.",
        dependencies=["AGENT_11"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_13",
        role=AgentRole.VISUAL_RESEARCH_DIRECTOR,
        name="Visual Research Director",
        description="Selects domain-appropriate visual archetypes (process animation, spatial map, comparison, anatomical model).",
        dependencies=["AGENT_12"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_14",
        role=AgentRole.STORYBOARD_ARCHITECT,
        name="Storyboard Architect",
        description="Assembles scene-by-scene storyboard linking narration sentences to visual assets, camera moves, and cues.",
        dependencies=["AGENT_13"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_15",
        role=AgentRole.ANIMATION_PLANNER,
        name="Animation Planner",
        description="Renders procedural step-by-step animations for complex processes and mechanisms.",
        dependencies=["AGENT_14"],
        is_retry_safe=True,
        has_side_effects=True,
    ),
    AgentTaskSpec(
        agent_id="AGENT_16",
        role=AgentRole.DIAGRAM_INFOGRAPHIC_PLANNER,
        name="Diagram and Infographic Planner",
        description="Renders custom institutional maps, comparative tables, timelines, and analytical charts.",
        dependencies=["AGENT_14"],
        is_retry_safe=True,
        has_side_effects=True,
    ),
    AgentTaskSpec(
        agent_id="AGENT_17",
        role=AgentRole.ASSET_RIGHTS_AUDITOR,
        name="Asset Rights Auditor",
        description="Inspects copyright, license terms, origins, and cryptographic hashes of all generated and included assets.",
        dependencies=["AGENT_15", "AGENT_16"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_18",
        role=AgentRole.NARRATION_DIRECTOR,
        name="Narration Director",
        description="Synthesizes verified licensed neural Hindi voice narration or prepares voice recording checklist.",
        dependencies=["AGENT_11", "AGENT_14"],
        is_retry_safe=True,
        has_side_effects=True,
    ),
    AgentTaskSpec(
        agent_id="AGENT_19",
        role=AgentRole.PRONUNCIATION_AUDITOR,
        name="Pronunciation Auditor",
        description="Validates pronunciation phonetic dictionary and audits code-switching accuracy for technical terminology.",
        dependencies=["AGENT_18"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_20",
        role=AgentRole.AUDIO_QUALITY_AUDITOR,
        name="Audio Quality Auditor",
        description="Measures audio loudness (LUFS), dynamic range, clipping prevention, and noise floor.",
        dependencies=["AGENT_18", "AGENT_19"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_21",
        role=AgentRole.SUBTITLE_TRANSLATION_AGENT,
        name="Subtitle and Translation Agent",
        description="Generates synchronized SRT/VTT subtitles (<21 CPS) and builds multilingual translation packages.",
        dependencies=["AGENT_20"],
        is_retry_safe=True,
        has_side_effects=True,
    ),
    AgentTaskSpec(
        agent_id="AGENT_22",
        role=AgentRole.VIDEO_QUALITY_AUDITOR,
        name="Video Quality Auditor",
        description="Composites scenes into final 1080p MP4, checking bitrate, AV synchronization, and render integrity.",
        dependencies=["AGENT_14", "AGENT_17", "AGENT_20", "AGENT_21"],
        is_retry_safe=False,  # Video rendering is a heavy side effect; requires explicit review on failure
        has_side_effects=True,
    ),
    AgentTaskSpec(
        agent_id="AGENT_23",
        role=AgentRole.ACADEMIC_RED_TEAM_REVIEWER,
        name="Academic Red-Team Reviewer",
        description="Performs adversarial review of claims, detects misleading simplifications, and verifies authentic PYQs.",
        dependencies=["AGENT_08", "AGENT_22"],
        is_retry_safe=True,
        has_side_effects=False,
    ),
    AgentTaskSpec(
        agent_id="AGENT_24",
        role=AgentRole.FINAL_RELEASE_GATEKEEPER,
        name="Final Release Gatekeeper",
        description="Enforces 10-gate quality certification (Gates A-J), human approval requirement, and release packaging.",
        dependencies=["AGENT_22", "AGENT_23"],
        is_retry_safe=False,  # Release gatekeeper has publishing implications
        has_side_effects=True,
    ),
]

# Backward-compatible alias for AGENT_REGISTRY dictionary format
AGENT_REGISTRY = [
    {
        "id": spec.agent_id,
        "name": spec.name,
        "role": spec.role.value,
        "description": spec.description,
        "dependencies": spec.dependencies,
        "is_retry_safe": spec.is_retry_safe,
        "has_side_effects": spec.has_side_effects,
        "max_retries": spec.max_retries,
    }
    for spec in SPECIALIST_REGISTRY
]
