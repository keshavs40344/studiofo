"""Tests for Phase 3-4: syllabus mapping, CSAT separation, explanatory depth, and evidence ledger."""

from __future__ import annotations

from pathlib import Path

import pytest

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, VerificationStatus
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.research.verifier import EvidenceEngine
from upsc_studio.syllabus.engine import SyllabusEngine


def test_syllabus_csat_not_confused_with_mains_gs2(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "studio.db")
    mgr = ProjectManager(conn, tmp_path / "projects")
    proj = mgr.create_project(ProjectCreate(name="Polity Ch1", chapter_title="Parliament and Anti-Defection Law"))

    engine = SyllabusEngine(conn)
    cmap = engine.map_chapter(
        proj.id,
        Path(proj.root_dir),
        "Parliament and Anti-Defection Law",
        notes_text="Anti-defection law in Tenth Schedule.",
    )
    papers = {p["paper"] for p in cmap["prelims_dimensions"] + cmap["mains_dimensions"]}
    assert "Mains GS Paper II" in papers
    assert "Prelims CSAT Paper II" not in papers


def test_keyword_only_is_partial_not_covered(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "studio.db")
    mgr = ProjectManager(conn, tmp_path / "projects")
    proj = mgr.create_project(ProjectCreate(name="Shallow Notes", chapter_title="Anti-Defection Law"))
    engine = SyllabusEngine(conn)

    cmap = engine.map_chapter(
        proj.id,
        Path(proj.root_dir),
        "Anti-Defection Law",
        notes_text="Parliament Tenth Schedule.",
    )
    assert len(cmap["missing_or_partial_topics"]) >= 1
    assert cmap["mains_dimensions"][0]["status"] == "PARTIAL"


def test_claim_verification_requires_source(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "studio.db")
    mgr = ProjectManager(conn, tmp_path / "projects")
    proj = mgr.create_project(ProjectCreate(name="Evidence Test", chapter_title="Anti-Defection Law"))
    ev = EvidenceEngine(conn, Path(proj.root_dir))

    with pytest.raises(ValueError):
        ev.add_claim(
            proj.id,
            "52nd Amendment Act 1985 added the Tenth Schedule.",
            "Historical Context",
            status=VerificationStatus.VERIFIED,
            source_id=None,
        )

    src_id = ev.add_source(
        proj.id,
        title="Constitution of India — Tenth Schedule",
        publisher="Legislative Department, Ministry of Law and Justice",
        source_tier="PRIMARY_OFFICIAL",
        url="https://legislative.gov.in/",
        pub_date="1985-02-15",
    )
    clm_id = ev.add_claim(
        proj.id,
        "The 52nd Amendment Act, 1985 inserted the Tenth Schedule into the Constitution.",
        "Historical Context",
        status=VerificationStatus.VERIFIED,
        source_id=src_id,
        page_or_section="Tenth Schedule",
    )
    ledger = ev.export_ledger(proj.id, "2026-11-26")
    assert ledger["status_counts"]["VERIFIED"] == 1
    assert clm_id.startswith("clm_")
