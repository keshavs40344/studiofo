"""Tests for MultiPassResearchWorkflow: claim categorization, cutoff date auditing, and fact gates."""

from __future__ import annotations

import sqlite3
from pathlib import Path
import pytest

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.research.multi_pass import ClaimNature, MultiPassResearchWorkflow, MultiPassStatus
from upsc_studio.research.verifier import EvidenceEngine


def test_multi_pass_research_claim_categorization_and_filtering(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "test_research.db")
    proj_mgr = ProjectManager(conn, tmp_path / "projects")
    proj = proj_mgr.create_project(
        ProjectCreate(
            name="Research Test Project",
            chapter_title="Constitutional Remedies under Article 32",
            exam_cycle="2026",
            cutoff_date="2026-11-26",
            target_duration_min=5,
            tts_enabled=True,
        )
    )

    ev_engine = EvidenceEngine(conn, Path(proj.root_dir))
    s1_id = ev_engine.add_source(
        project_id=proj.id,
        title="Constitution of India",
        publisher="Government of India",
        source_tier="PRIMARY_OFFICIAL",
        pub_date="2024-01-01",
    )
    s2_future_id = ev_engine.add_source(
        project_id=proj.id,
        title="Hypothetical Future Report 2028",
        publisher="Future Think Tank",
        source_tier="OTHER",
        pub_date="2028-06-01",
    )

    # 1. Fact with valid pinpoint reference -> Safe for narration
    supported_claim_id = ev_engine.add_claim(
        project_id=proj.id,
        statement="Article 32 confers right to approach the Supreme Court for enforcement of Fundamental Rights.",
        chapter_section="Remedies",
        source_id=s1_id,
        page_or_section="Article 32, Clause 1",
        ref_period="2024",
    )
    ev_engine.verify_claim_against_source(
        claim_id=supported_claim_id,
        source_id=s1_id,
        page_or_section="Article 32, Clause 1",
        evidence_excerpt="The right to move the Supreme Court by appropriate proceedings for enforcement of Part III rights.",
        reviewer_id="test-reviewer",
    )

    # 2. Unsupported claim (missing source and page) -> Must be marked INSUFFICIENT_EVIDENCE
    ev_engine.add_claim(
        project_id=proj.id,
        statement="Some unsubstantiated assertion without verified documentation.",
        chapter_section="Unverified",
        source_id=None,
        page_or_section=None,
    )

    # 3. Interpretation claim -> Classified as INTERPRETATION
    ev_engine.add_claim(
        project_id=proj.id,
        statement="It could be argued that writ jurisdiction has expanded judicial supremacy beyond original intent.",
        chapter_section="Debates",
        source_id=s1_id,
        page_or_section="Chapter 4, Page 88",
    )

    # 4. Outdated / Future source claim -> Flagged OUTDATED
    ev_engine.add_claim(
        project_id=proj.id,
        statement="Projections show legal cases will double by 2028 according to the 2028 report.",
        chapter_section="Future Projections",
        source_id=s2_future_id,
        page_or_section="Page 10",
    )

    workflow = MultiPassResearchWorkflow(conn, Path(proj.root_dir))
    report = workflow.run_multi_pass_audit(proj.id, proj.chapter_title, proj.cutoff_date)

    assert report.total_claims_extracted == 4
    assert report.verified_facts_count == 1
    assert report.safe_narration_claims[0].claim_id == supported_claim_id
    assert report.interpretations_count >= 1
    assert report.insufficient_evidence_count >= 1
    assert report.outdated_claims_count >= 1

    # Verify that unsupported and outdated claims are filtered out from safe_narration_claims
    safe_stmts = [c.statement for c in report.safe_narration_claims]
    assert any("Article 32 confers right" in s for s in safe_stmts)
    assert not any("unsubstantiated assertion" in s for s in safe_stmts)

    excluded_stmts = [c.statement for c in report.excluded_claims]
    assert any("unsubstantiated assertion" in s for s in excluded_stmts)

    # Verify SQLite was updated with INSUFFICIENT_EVIDENCE status notes
    rows = conn.execute("SELECT status, verification_notes FROM claims WHERE source_id IS NULL").fetchall()
    assert len(rows) > 0
    assert rows[0]["status"] == "UNSUPPORTED"
    assert "INSUFFICIENT_EVIDENCE" in rows[0]["verification_notes"]
