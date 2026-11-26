"""Multi-agent contracts, dependency graph, and execution statuses for UPSC Studio."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    REGISTERED = "REGISTERED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


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


# 24 production agents arranged as a dependency-aware task graph.
# Dependencies explicitly specify which upstream agent(s) must complete before an agent runs.
AGENT_REGISTRY: list[dict[str, Any]] = [
    {
        "id": "AGENT_01",
        "name": "Executive Producer / Supervisor",
        "module": "upsc_studio.agents.supervisor.ExecutiveProducer",
        "dependencies": [],
        "description": "Supervises task graph execution, checkpoints, retries, and overall delivery.",
    },
    {
        "id": "AGENT_02",
        "name": "UPSC Syllabus Expert",
        "module": "upsc_studio.syllabus.engine.SyllabusEngine",
        "dependencies": ["AGENT_01"],
        "description": "Maps chapter to official UPSC Prelims and Mains syllabus requirements.",
    },
    {
        "id": "AGENT_03",
        "name": "Research Intelligence Agent",
        "module": "upsc_studio.ingestion.ingestor.DocumentIngestor",
        "dependencies": ["AGENT_01"],
        "description": "Extracts text, preserves source document provenance and handles uploads.",
    },
    {
        "id": "AGENT_04",
        "name": "Independent Fact-Checking Agent",
        "module": "upsc_studio.research.verifier.EvidenceEngine",
        "dependencies": ["AGENT_02", "AGENT_03"],
        "description": "Decomposes atomic claims, manages source tiers, and detects conflicts.",
    },
    {
        "id": "AGENT_05",
        "name": "Academic Teacher Agent",
        "module": "upsc_studio.academic.specialists.SpecialistProfileEngine",
        "dependencies": ["AGENT_02"],
        "description": "Selects GS specialist pedagogy (GS1/GS2/GS3/GS4) and learning objectives.",
    },
    {
        "id": "AGENT_06",
        "name": "Storytelling & Retention Director",
        "module": "upsc_studio.publishing.editorial_optimizer.EditorialOptimizer",
        "dependencies": ["AGENT_05"],
        "description": "Plans retention hooks, conceptual transitions, and pedagogical pacing.",
    },
    {
        "id": "AGENT_07",
        "name": "Scriptwriter",
        "module": "upsc_studio.teaching.engine.TeachingEngine",
        "dependencies": ["AGENT_04", "AGENT_05", "AGENT_06"],
        "description": "Generates verified Hinglish teaching scripts and study materials.",
    },
    {
        "id": "AGENT_08",
        "name": "Script Red-Team Editor",
        "module": "upsc_studio.academic.pyq_engine.PYQEngine",
        "dependencies": ["AGENT_07"],
        "description": "Validates authenticity of PYQs and checks for ungrounded claims in script.",
    },
    {
        "id": "AGENT_09",
        "name": "Pronunciation & Language Agent",
        "module": "upsc_studio.tts.pronunciation.PronunciationNormalizer",
        "dependencies": ["AGENT_07"],
        "description": "Normalizes Hinglish phonetics and Hindi terminology for audio synthesis.",
    },
    {
        "id": "AGENT_10",
        "name": "Visual Research Agent",
        "module": "upsc_studio.graphics.rights.AssetRightsLedger",
        "dependencies": ["AGENT_07"],
        "description": "Checks copyright licensing, public domain status, and asset provenance.",
    },
    {
        "id": "AGENT_11",
        "name": "Documentary Visual Director",
        "module": "upsc_studio.storyboard.director.StoryboardDirector",
        "dependencies": ["AGENT_07", "AGENT_10"],
        "description": "Directs scene-by-scene storyboard, camera flow, and visual typology.",
    },
    {
        "id": "AGENT_12",
        "name": "Map & Geo-Spatial Agent",
        "module": "upsc_studio.integrations.qgis_map.MapVisualEngine",
        "dependencies": ["AGENT_11"],
        "description": "Generates institutional jurisdiction and geographical locator maps.",
    },
    {
        "id": "AGENT_13",
        "name": "Motion Graphics & Animation Agent",
        "module": "upsc_studio.integrations.manim_worker.AnimationEngine",
        "dependencies": ["AGENT_11"],
        "description": "Renders procedural step-by-step constitutional and process animations.",
    },
    {
        "id": "AGENT_14",
        "name": "Data Visualisation Agent",
        "module": "upsc_studio.integrations.altair_charts.AltairChartAdapter",
        "dependencies": ["AGENT_11"],
        "description": "Renders statistical trend charts, Vega-Lite specs, and comparison tables.",
    },
    {
        "id": "AGENT_15",
        "name": "AI Narration Agent",
        "module": "upsc_studio.tts.adapter.PiperTTSEngine",
        "dependencies": ["AGENT_09", "AGENT_11"],
        "description": "Synthesizes verified licensed Hindi voice or flags voice requirements.",
    },
    {
        "id": "AGENT_16",
        "name": "Documentary Video Editor",
        "module": "upsc_studio.video.renderer.VideoRenderer",
        "dependencies": ["AGENT_11", "AGENT_12", "AGENT_13", "AGENT_14", "AGENT_15"],
        "description": "Assembles scene timeline, transitions, muxes audio, and renders final MP4.",
    },
    {
        "id": "AGENT_17",
        "name": "Audio Engineer",
        "module": "upsc_studio.audio.processor.VoiceAudioProcessor",
        "dependencies": ["AGENT_15"],
        "description": "Performs loudness normalization, clipping prevention, and silence audit.",
    },
    {
        "id": "AGENT_18",
        "name": "Subtitle & Accessibility Agent",
        "module": "upsc_studio.audio.processor.VoiceAudioProcessor",
        "dependencies": ["AGENT_17"],
        "description": "Aligns sentence-level timings into synchronized SRT subtitles.",
    },
    {
        "id": "AGENT_19",
        "name": "Thumbnail & Visual Packaging Agent",
        "module": "upsc_studio.graphics.publishing.PublishingPackageBuilder",
        "dependencies": ["AGENT_11"],
        "description": "Generates 1280x720 thumbnail and title/description metadata pack.",
    },
    {
        "id": "AGENT_20",
        "name": "YouTube Discovery & SEO Agent",
        "module": "upsc_studio.publishing.editorial_optimizer.EditorialOptimizer",
        "dependencies": ["AGENT_19"],
        "description": "Produces educational YouTube Shorts candidates, tags, and chapter markers.",
    },
    {
        "id": "AGENT_21",
        "name": "Copyright & Policy Agent",
        "module": "upsc_studio.qa.auditor.QAAuditor",
        "dependencies": ["AGENT_10", "AGENT_16"],
        "description": "Audits rights clearance ledger and budget/licensing policies.",
    },
    {
        "id": "AGENT_22",
        "name": "Final Quality Auditor",
        "module": "upsc_studio.qa.ten_gates.TenGateAuditor",
        "dependencies": ["AGENT_16", "AGENT_18", "AGENT_21"],
        "description": "Evaluates 10-gate quality certification (Gates A through J).",
    },
    {
        "id": "AGENT_23",
        "name": "YouTube Publishing Agent",
        "module": "upsc_studio.publishing.youtube_publisher.YouTubePublisher",
        "dependencies": ["AGENT_22"],
        "description": "Validates OAuth, human publication approval, and executes private upload.",
    },
    {
        "id": "AGENT_24",
        "name": "Analytics & Improvement Agent",
        "module": "upsc_studio.publishing.youtube_publisher.YouTubeAnalyticsAgent",
        "dependencies": ["AGENT_23"],
        "description": "Monitors retention analytics and flags editorial improvement items.",
    },
]
