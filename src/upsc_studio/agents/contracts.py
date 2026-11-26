"""Multi-agent contracts and 24-agent registry mapped to real executable modules."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AgentTaskResult(BaseModel):
    task_id: str
    agent_id: str
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)
    status: str  # COMPLETED | FAILED | BLOCKED | PENDING
    execution_time_sec: float = 0.0
    errors: list[str] = Field(default_factory=list)
    retry_count: int = 0
    verification_status: str = "PENDING_INDEPENDENT_REVIEW"
    next_dependency: Optional[str] = None


AGENT_REGISTRY: list[dict] = [
    {"id": "AGENT_01", "name": "Executive Producer / Supervisor", "module": "upsc_studio.agents.supervisor.ExecutiveProducer"},
    {"id": "AGENT_02", "name": "UPSC Syllabus Expert", "module": "upsc_studio.syllabus.engine.SyllabusEngine"},
    {"id": "AGENT_03", "name": "Research Intelligence Agent", "module": "upsc_studio.ingestion.ingestor.DocumentIngestor"},
    {"id": "AGENT_04", "name": "Independent Fact-Checking Agent", "module": "upsc_studio.research.verifier.EvidenceEngine"},
    {"id": "AGENT_05", "name": "Academic Teacher Agent", "module": "upsc_studio.academic.specialists.SpecialistProfileEngine"},
    {"id": "AGENT_06", "name": "Storytelling & Retention Director", "module": "upsc_studio.publishing.editorial_optimizer.EditorialOptimizer"},
    {"id": "AGENT_07", "name": "Scriptwriter", "module": "upsc_studio.teaching.engine.TeachingEngine"},
    {"id": "AGENT_08", "name": "Script Red-Team Editor", "module": "upsc_studio.academic.pyq_engine.PYQEngine"},
    {"id": "AGENT_09", "name": "Pronunciation & Language Agent", "module": "upsc_studio.tts.pronunciation.PronunciationNormalizer"},
    {"id": "AGENT_10", "name": "Visual Research Agent", "module": "upsc_studio.graphics.rights.AssetRightsLedger"},
    {"id": "AGENT_11", "name": "Documentary Visual Director", "module": "upsc_studio.storyboard.director.StoryboardDirector"},
    {"id": "AGENT_12", "name": "Map & Geo-Spatial Agent", "module": "upsc_studio.integrations.qgis_map.MapVisualEngine"},
    {"id": "AGENT_13", "name": "Motion Graphics & Animation Agent", "module": "upsc_studio.integrations.manim_worker.AnimationEngine"},
    {"id": "AGENT_14", "name": "Data Visualisation Agent", "module": "upsc_studio.integrations.altair_charts.AltairChartAdapter"},
    {"id": "AGENT_15", "name": "AI Narration Agent", "module": "upsc_studio.tts.adapter.PiperTTSEngine"},
    {"id": "AGENT_16", "name": "Documentary Video Editor", "module": "upsc_studio.video.renderer.VideoRenderer"},
    {"id": "AGENT_17", "name": "Audio Engineer", "module": "upsc_studio.audio.processor.VoiceAudioProcessor"},
    {"id": "AGENT_18", "name": "Subtitle & Accessibility Agent", "module": "upsc_studio.audio.processor.VoiceAudioProcessor"},
    {"id": "AGENT_19", "name": "Thumbnail & Visual Packaging Agent", "module": "upsc_studio.graphics.publishing.PublishingPackageBuilder"},
    {"id": "AGENT_20", "name": "YouTube Discovery & SEO Agent", "module": "upsc_studio.publishing.editorial_optimizer.EditorialOptimizer"},
    {"id": "AGENT_21", "name": "Copyright & Policy Agent", "module": "upsc_studio.qa.auditor.QAAuditor"},
    {"id": "AGENT_22", "name": "Final Quality Auditor", "module": "upsc_studio.qa.ten_gates.TenGateAuditor"},
    {"id": "AGENT_23", "name": "YouTube Publishing Agent", "module": "upsc_studio.publishing.youtube_publisher.YouTubePublisher"},
    {"id": "AGENT_24", "name": "Analytics & Improvement Agent", "module": "upsc_studio.publishing.youtube_publisher.YouTubeAnalyticsAgent"},
]
