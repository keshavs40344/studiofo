"""Pydantic domain schemas and enums for UPSC Studio."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    CONFLICTING = "CONFLICTING"
    OUTDATED = "OUTDATED"
    UNSUPPORTED = "UNSUPPORTED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class CoverageStatus(str, Enum):
    COVERED = "COVERED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class RightsStatus(str, Enum):
    ORIGINAL_GENERATED = "ORIGINAL_GENERATED"
    USER_OWNED = "USER_OWNED"
    PUBLIC_DOMAIN = "PUBLIC_DOMAIN"
    LICENSED = "LICENSED"
    UNVERIFIED = "UNVERIFIED"


class ProjectStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    PROCESSING = "PROCESSING"
    WAITING_FOR_VOICE = "WAITING_FOR_VOICE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"
    APPROVED = "APPROVED"
    EXPORTED = "EXPORTED"


class QAGateName(str, Enum):
    ACADEMICALLY_REVIEWED = "ACADEMICALLY_REVIEWED"
    RIGHTS_CLEARED = "RIGHTS_CLEARED"
    VIDEO_TECHNICALLY_APPROVED = "VIDEO_TECHNICALLY_APPROVED"
    READY_FOR_PUBLICATION = "READY_FOR_PUBLICATION"


class QAGateStatus(str, Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    chapter_title: str = Field(..., min_length=2, max_length=200)
    content_category: Literal["upsc", "general_knowledge", "current_affairs", "deep_dive"] = "upsc"
    exam_cycle: str = Field(default="UPSC CSE 2026")
    cutoff_date: str = Field(default_factory=lambda: datetime.now().astimezone().date().isoformat())
    target_duration_min: int = Field(default=30, ge=1, le=180)
    tts_enabled: bool = Field(default=False)


class ProjectRecord(ProjectCreate):
    id: str
    slug: str
    root_dir: str
    status: ProjectStatus = ProjectStatus.NOT_STARTED
    created_at: str
    updated_at: str


class ClaimRecord(BaseModel):
    id: str
    project_id: str
    statement: str
    chapter_section: str
    scene_id: Optional[str] = None
    source_id: Optional[str] = None
    page_or_section: Optional[str] = None
    ref_period: Optional[str] = None
    status: VerificationStatus = VerificationStatus.UNSUPPORTED
    verification_notes: str = ""


class SceneSpec(BaseModel):
    scene_id: str
    section_id: str
    section_title: str
    learning_objective: str
    narration_text: str
    claim_ids: list[str] = Field(default_factory=list)
    estimated_duration_sec: float
    visual_category: str
    primary_asset: Optional[str] = None
    supporting_asset: Optional[str] = None
    asset_rights_status: RightsStatus = RightsStatus.ORIGINAL_GENERATED
    on_screen_title: str
    on_screen_bullets: list[str] = Field(default_factory=list)
    animation_type: str = "fade_in"
    transition_in: str = "cross_dissolve"
    transition_out: str = "hard_cut"
    audio_cue: str = "narration_only"
    source_citations: list[str] = Field(default_factory=list)
    qc_status: str = "PENDING"
    metadata: dict[str, Any] = Field(default_factory=dict)

class ResearchDiscoveryRequest(BaseModel):
    query: str = Field(..., min_length=4, max_length=300)
    limit: int = Field(default=8, ge=1, le=10)


class ResearchSourceCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=300)
    publisher: str = Field(..., min_length=2, max_length=200)
    source_tier: Literal[
        "PRIMARY_OFFICIAL", "ACADEMIC_PEER_REVIEWED", "REPUTABLE_NEWS", "OTHER"
    ]
    url: str = Field(..., min_length=8, max_length=2000)
    pub_date: str | None = Field(default=None, max_length=40)
    notes: str = Field(default="", max_length=3000)


class ResearchClaimCreate(BaseModel):
    statement: str = Field(..., min_length=20, max_length=3000)
    chapter_section: str = Field(..., min_length=2, max_length=200)
    source_id: str | None = None
    page_or_section: str | None = Field(default=None, max_length=300)
    ref_period: str | None = Field(default=None, max_length=100)


class ClaimVerificationRequest(BaseModel):
    source_id: str = Field(..., min_length=4, max_length=80)
    page_or_section: str = Field(..., min_length=2, max_length=300)
    evidence_excerpt: str = Field(..., min_length=10, max_length=5000)
    reviewer: str = Field(..., min_length=2, max_length=120)
    ref_period: str | None = Field(default=None, max_length=100)


class ManualRetryRequest(BaseModel):
    reviewer: str = Field(..., min_length=2, max_length=120)
    reason: str = Field(..., min_length=5, max_length=1000)
    partial_outputs_inspected: bool = False


class ManualQAReview(BaseModel):
    """Explicit creator checklist for quality items automation cannot certify."""

    reviewer: str = Field(..., min_length=2, max_length=120)
    content_scope_coverage: bool = False
    teaching_clarity: bool = False
    visual_relevance: bool = False
    voice_subtitle_alignment: bool = False
    final_playback_inspection: bool = False
    notes: str = Field(default="", max_length=2000)

