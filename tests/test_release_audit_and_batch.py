"""Tests for ReleaseAuditGenerator and BatchProductionOrchestrator."""

from __future__ import annotations

import json
from pathlib import Path

from upsc_studio.automation.batch_runner import BatchJobItem, BatchProductionOrchestrator
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, ProjectStatus, VerificationStatus
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.qa.release_audit import ReleaseAuditGenerator
from upsc_studio.research.verifier import EvidenceEngine


def test_release_audit_generator_separates_gates_and_tracks_artifacts(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "audit.db")
    projects_root = tmp_path / "projects"
    mgr = ProjectManager(conn, projects_root)
    proj = mgr.create_project(ProjectCreate(name="Audit Test", chapter_title="Indus Valley Civilization"))
    proj_dir = Path(proj.root_dir)

    # Create dummy script & storyboard
    (proj_dir / "teaching").mkdir(parents=True, exist_ok=True)
    (proj_dir / "teaching" / "script_hinglish.md").write_text("# Indus Valley\nVerified lesson.", encoding="utf-8")
    (proj_dir / "storyboard").mkdir(parents=True, exist_ok=True)
    (proj_dir / "storyboard" / "storyboard.json").write_text("[]", encoding="utf-8")

    # Add verified source & claim
    ev = EvidenceEngine(conn, proj_dir)
    src_id = ev.add_source(proj.id, "NCERT Class XII History", "NCERT", "PRIMARY_OFFICIAL", "https://ncert.nic.in")
    ev.add_claim(
        proj.id,
        "Harappa was excavated in 1921 by Daya Ram Sahni.",
        "Discovery",
        status=VerificationStatus.VERIFIED,
        source_id=src_id,
        page_or_section="Chapter 1, Page 1",
    )

    res = ReleaseAuditGenerator(conn, proj_dir).generate(proj.id)
    assert Path(res["release_candidate_json"]).is_file()
    assert Path(res["release_report_md"]).is_file()

    cand = res["candidate"]
    assert "ACADEMICALLY_REVIEWED" in cand["core_gates"]
    assert "RIGHTS_CLEARED" in cand["core_gates"]
    assert "VIDEO_TECHNICALLY_APPROVED" in cand["core_gates"]
    assert "READY_FOR_PUBLICATION" in cand["core_gates"]
    assert cand["public_upload_authorized"] is False  # Missing video & manual approval
    assert cand["artifacts"]["script_hinglish"]["size_bytes"] > 0


def test_batch_orchestrator_skips_approved_and_throttles_on_low_ram(tmp_path: Path, monkeypatch) -> None:
    conn = init_db(tmp_path / "batch.db")
    projects_root = tmp_path / "projects"
    mgr = ProjectManager(conn, projects_root)
    p1 = mgr.create_project(ProjectCreate(name="P1", chapter_title="Topic 1"))
    p2 = mgr.create_project(ProjectCreate(name="P2", chapter_title="Topic 2"))
    mgr.update_status(p1.id, ProjectStatus.APPROVED)

    orch = BatchProductionOrchestrator(conn, projects_root, max_ram_percent=95.0, min_free_disk_gb=0.1)
    executed = []

    def fake_runner(item: BatchJobItem) -> dict:
        executed.append(item.project_id)
        return {"status": "COMPLETED"}

    res = orch.run_batch(
        [BatchJobItem(project_id=p1.id), BatchJobItem(project_id=p2.id), BatchJobItem(project_id="nonexistent")],
        skip_approved=True,
        runner_fn=fake_runner,
    )
    assert res["skipped"] == 1
    assert res["completed"] == 1
    assert res["failed"] == 1
    assert executed == [p2.id]

    # Now test RAM throttle
    class HighMem:
        percent = 99.0
        total = 16 * 1024**3
        available = 128 * 1024**2
    import psutil
    monkeypatch.setattr(psutil, "virtual_memory", lambda: HighMem())
    res_throttled = orch.run_batch([BatchJobItem(project_id=p2.id)], skip_approved=True, runner_fn=fake_runner)
    assert res_throttled["paused_or_blocked"] == 1
    assert res_throttled["results"][0]["batch_status"] == "THROTTLED_RESOURCE_GUARD"
