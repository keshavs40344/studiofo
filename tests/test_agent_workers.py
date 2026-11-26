from upsc_studio.agents.workers import (
    coverage_audit, evidence_completeness_audit, release_gate,
    rights_asset_audit, topic_profile,
)


def test_topic_profile_requires_explicit_category_and_current_affairs_cutoff():
    assert topic_profile({"category": "science"})["status"] == "REVIEW_REQUIRED"
    assert topic_profile({"category": "current_affairs"})["status"] == "BLOCKED"
    result = topic_profile({"category": "general_knowledge"})
    assert result["status"] == "COMPLETED"
    assert result["syllabus_mapping_enabled"] is False


def test_coverage_audit_detects_omitted_required_concept():
    result = coverage_audit({
        "required_concepts": ["photosynthesis", "chlorophyll"],
        "script_text": "Photosynthesis converts light energy into chemical energy.",
    })
    assert result["status"] == "FAILED"
    assert result["missing"] == ["chlorophyll"]


def test_evidence_audit_flags_missing_sources_and_dates():
    result = evidence_completeness_audit({"claims": [{"text": "Claim without citation"}]})
    assert result["status"] == "REVIEW_REQUIRED"
    assert {x["reason"] for x in result["issues"]} == {"source_refs_missing", "source_date_missing"}


def test_rights_audit_blocks_unverified_assets():
    result = rights_asset_audit({"assets": [{"asset_ref": "img-1", "origin": "download"}]})
    assert result["status"] == "FAILED"
    assert result["issues"][0]["reason"] == "rights_not_verified"


def test_release_gate_never_authorizes_public_upload():
    result = release_gate({"gates": {"academic": {"status": "PASSED"}},
                           "human_release_approval": True})
    assert result["status"] == "RELEASE_READY"
    assert result["public_upload_authorized"] is False
