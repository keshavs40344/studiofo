"""Tests for Phase 15: 24-agent supervisor, retry recovery, Piper Hindi TTS, Shorts, and YouTube privacy rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from upsc_studio.agents.contracts import AGENT_REGISTRY
from upsc_studio.agents.supervisor import ExecutiveProducer
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, VerificationStatus
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.publishing.youtube_publisher import (
    DEFAULT_PRIVACY_STATUS,
    YouTubePublisher,
)
from upsc_studio.research.verifier import EvidenceEngine
from upsc_studio.tts.pronunciation import PronunciationNormalizer


def test_agent_registry_and_retry_recovery(tmp_path: Path) -> None:
    assert len(AGENT_REGISTRY) == 24
    conn = init_db(tmp_path / "ag.db")

    sup = ExecutiveProducer(conn, tmp_path / "projects")

    attempts = {"count": 0}

    def flaky() -> dict:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TimeoutError("Transient network timeout")
        return {"output": "ok"}

    res, out = sup.run_with_retry("AGENT_03", flaky, input_refs=["doc_1"], max_retries=2)
    assert res.status == "COMPLETED"
    assert res.retry_count == 1
    assert out == {"output": "ok"}


def test_pronunciation_normalizer() -> None:
    norm = PronunciationNormalizer()
    text = "UPSC Prelims mein Article 32 aur Supreme Court ke Writs par question aata hai."
    spoken, applied = norm.normalize(text)
    assert "आर्टिकल" in spoken
    assert "सुप्रीम कोर्ट" in spoken
    assert "रिट्स" in spoken
    assert len(applied) >= 4


def test_youtube_publisher_enforces_private_default_and_oauth(tmp_path: Path) -> None:
    assert DEFAULT_PRIVACY_STATUS == "private"
    yt = YouTubePublisher(token_path=tmp_path / "missing_token.json")
    mp4 = tmp_path / "video.mp4"
    mp4.write_bytes(b"fake_mp4_bytes")

    res_blocked_qa = yt.upload_video(mp4, {"video_title": "Test"}, qa_passed=False)
    assert res_blocked_qa["status"] == "BLOCKED_QA_FAILED"

    public_without_approval = yt.upload_video(
        mp4, {"video_title": "Test"}, qa_passed=True, privacy_status="public"
    )
    assert public_without_approval["status"] == "BLOCKED_AWAITING_EXPLICIT_USER_APPROVAL"

    res_pending = yt.upload_video(mp4, {"video_title": "Test"}, qa_passed=True, privacy_status="private")
    assert res_pending["status"] == "BLOCKED_AWAITING_EXPLICIT_USER_APPROVAL"


def test_autonomous_factory_no_user_voice_with_piper_tts(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "factory.db")
    mgr = ProjectManager(conn, tmp_path / "projects")
    proj = mgr.create_project(
        ProjectCreate(
            name="FR Autonomous Factory",
            chapter_title="Fundamental Rights of the Indian Constitution",
            target_duration_min=5,
        )
    )
    proj_dir = Path(proj.root_dir)

    ev = EvidenceEngine(conn, proj_dir)
    src = ev.add_source(
        proj.id,
        title="Constitution of India — Part III",
        publisher="Ministry of Law and Justice",
        source_tier="PRIMARY_OFFICIAL",
        url="https://legislative.gov.in/",
        pub_date="2024-05-01",
    )
    claim_id = ev.add_claim(
        proj.id,
        "Part III (Articles 12-35) guarantees Fundamental Rights.",
        "Constitutional Basis",
        status=VerificationStatus.VERIFIED,
        source_id=src,
        page_or_section="Part III",
    )
    ev.verify_claim_against_source(
        claim_id,
        src,
        "Part III, Articles 12-35",
        "Part III contains the provisions relating to Fundamental Rights.",
        reviewer_id="factory-test-reviewer",
    )

    sup = ExecutiveProducer(conn, tmp_path / "projects")
    out = sup.run_autonomous_factory(proj.id, ai_narration=True, youtube_token_path=tmp_path / "no_oauth.json")

    assert out["agents_registered"] == 24
    assert out["supervisor_task"]["status"] == "COMPLETED"
    assert Path(out["audio_report"]["narration_full_wav"]).exists()
    assert Path(out["audio_report"]["narration_transcript_srt"]).exists()
    assert Path(out["audio_report"]["pronunciation_report"]).exists()
    assert Path(out["render_manifest"]["final_video"]).exists()
    assert Path(out["render_manifest"]["final_video"]).stat().st_size > 20000
    assert len(out["editorial_and_shorts"]["shorts_candidates"]) >= 1
    assert out["youtube_publish"]["status"] == "BLOCKED_AWAITING_EXPLICIT_PUBLISH_APPROVAL"
