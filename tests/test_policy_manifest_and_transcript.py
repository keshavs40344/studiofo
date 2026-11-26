"""Tests for budget/cloud policy guard, resumable job manifest, temp cleanup, and script-transcript comparison."""

from __future__ import annotations

from pathlib import Path

import pytest

from upsc_studio.audio.processor import VoiceAudioProcessor
from upsc_studio.core.policy import (
    DEFAULT_POLICY,
    PaidActionBlockedError,
    require_cloud_upload_approval,
    require_paid_approval,
)
from upsc_studio.pipeline.job_manifest import JobManifestManager


def test_budget_and_cloud_policy_blocks_unapproved_paid_actions() -> None:
    assert DEFAULT_POLICY.FREE_FIRST is True
    assert DEFAULT_POLICY.LOCAL_FIRST is True
    assert DEFAULT_POLICY.PAID_SERVICES_ENABLED is False
    assert DEFAULT_POLICY.PAID_API_CALLS_ENABLED is False

    with pytest.raises(PaidActionBlockedError):
        require_paid_approval(
            provider="OpenAI",
            purpose="Cloud TTS",
            estimated_cost_inr=120.0,
            free_alternative_reason="User own voice is default",
        )

    with pytest.raises(PaidActionBlockedError):
        require_cloud_upload_approval("ExternalCloud")


def test_job_manifest_checkpoint_and_temp_cleanup(tmp_path: Path) -> None:
    (tmp_path / "inputs" / "originals").mkdir(parents=True)
    (tmp_path / "inputs" / "uploads_tmp").mkdir(parents=True)
    orig = tmp_path / "inputs" / "originals" / "notes.pdf"
    orig.write_text("keep original", encoding="utf-8")
    tmp_file = tmp_path / "inputs" / "uploads_tmp" / "tmp_notes.pdf"
    tmp_file.write_text("transient", encoding="utf-8")

    jm = JobManifestManager(tmp_path)
    assert jm.is_stage_completed("research") is False
    jm.mark_stage("research", "COMPLETED", {"claims": 5})
    assert jm.is_stage_completed("research") is True

    removed = jm.cleanup_temp_files()
    assert removed == 1
    assert not tmp_file.exists()
    assert orig.exists()


def test_transcript_to_script_comparison() -> None:
    script = (
        "52nd Amendment Act 1985 inserted the Tenth Schedule. "
        "Kihoto Hollohan judgment confirmed judicial review."
    )
    transcript = (
        "52nd Amendment Act 1985 inserted the Tenth Schedule. "
        "Yeh extra sentence script mein nahi tha."
    )
    diff = VoiceAudioProcessor.compare_transcript_to_script(script, transcript)
    assert len(diff["missing_sentences"]) == 1
    assert "Kihoto Hollohan" in diff["missing_sentences"][0]
    assert len(diff["extra_sentences"]) == 1
    assert diff["requires_retake_or_review"] is True
