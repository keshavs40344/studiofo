from upsc_studio.agents.workers import (
    build_quality_review_tasks, coverage_audit, evidence_completeness_audit, release_gate,
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



def test_quality_workflow_reaches_release_ready_only_after_all_audits_and_approval():
    import sqlite3
    from upsc_studio.agents.runtime import AgentTaskStore, DependencyScheduler
    from upsc_studio.agents.workers import default_worker_handlers

    conn = sqlite3.connect(":memory:")
    scheduler = DependencyScheduler(AgentTaskStore(conn), default_worker_handlers())
    specs = build_quality_review_tasks(
        {"category": "general_knowledge"},
        {"required_concepts": ["photosynthesis"], "script_text": "Photosynthesis converts light energy."},
        {"claims": [{"text": "Photosynthesis uses light", "source_refs": ["SRC-1"], "source_date": "2026-01-01"}]},
        {"assets": [{"asset_ref": "ASSET-1", "source_url": "https://example.org/a",
                     "rights_status": "LICENSED"}]},
        human_release_approval=True,
    )
    result = scheduler.run("quality-approved", specs)
    assert result["status"] == "COMPLETED"
    assert result["completed"] == 5
    assert result["tasks"][-1]["output_json"] == '{"failed_gates": [], "note": "Release readiness never triggers upload; public publishing remains a separate explicit action.", "public_upload_authorized": false, "status": "RELEASE_READY"}'


def test_quality_workflow_cannot_release_without_human_approval():
    import sqlite3
    from upsc_studio.agents.runtime import AgentTaskStore, DependencyScheduler
    from upsc_studio.agents.workers import default_worker_handlers

    conn = sqlite3.connect(":memory:")
    scheduler = DependencyScheduler(AgentTaskStore(conn), default_worker_handlers())
    specs = build_quality_review_tasks(
        {"category": "general_knowledge"},
        {"required_concepts": ["gravity"], "script_text": "Gravity attracts masses."},
        {"claims": []},
        {"assets": []},
        human_release_approval=False,
    )
    result = scheduler.run("quality-no-approval", specs)
    assert result["status"] == "BLOCKED"
    assert result["blocked"] == 1
