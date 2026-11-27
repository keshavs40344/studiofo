"""End-to-end integration tests: WAITING_FOR_VOICE, real WAV + FFmpeg MP4 render, QA gates, and FastAPI."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from fastapi.testclient import TestClient

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, VerificationStatus
from upsc_studio.pipeline.orchestrator import ChapterPipeline
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.qa.auditor import QAAuditor
from upsc_studio.research.verifier import EvidenceEngine
from upsc_studio.web.app import create_app


def _write_test_wav(path: Path, duration_sec: float = 4.0, freq_hz: float = 220.0) -> None:
    """Create a real non-silent PCM WAV file for audio/FFmpeg pipeline testing."""
    sample_rate = 44100
    n_samples = int(sample_rate * duration_sec)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            val = int(12000 * math.sin(2.0 * math.pi * freq_hz * (i / sample_rate)))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(bytes(frames))


def test_end_to_end_waiting_for_voice_then_full_mp4_render(tmp_path: Path) -> None:
    db_path = tmp_path / "studio.db"
    projects_root = tmp_path / "projects"
    conn = init_db(db_path)
    mgr = ProjectManager(conn, projects_root)

    proj = mgr.create_project(
        ProjectCreate(
            name="Anti-Defection Law Demo",
            chapter_title="Anti-Defection Law and Tenth Schedule",
            exam_cycle="UPSC CSE 2026",
            cutoff_date="2026-11-26",
        )
    )
    proj_dir = Path(proj.root_dir)

    sample_notes = tmp_path / "chapter_notes.md"
    sample_notes.write_text(
        "# Anti-Defection Law\n\n"
        "The Anti-Defection Law refers to the Tenth Schedule, which was added by the 52nd Amendment Act 1985. "
        "Its mechanism empowers the Presiding Officer to decide disqualification petitions under Article 102(2). "
        "For example, in Kihoto Hollohan (1992), the Supreme Court held that the Speaker's decision is subject to judicial review. "
        "A major challenge is the lack of a fixed time limit for the Speaker's decision.",
        encoding="utf-8",
    )

    pipeline = ChapterPipeline(conn, projects_root)

    # Stage A: Ingest notes, but block narration until each extracted claim is reviewed.
    res_no_voice = pipeline.run_pipeline(proj.id, notes_files=[sample_notes])
    assert res_no_voice["status"] == "WAITING_FOR_RESEARCH_REVIEW"
    assert res_no_voice["claims_count"] >= 1
    assert res_no_voice["pending_claims_count"] == res_no_voice["claims_count"]

    # Stage B: Reviewer inspects the original source and attests each claim excerpt.
    ev = EvidenceEngine(conn, proj_dir)
    src_id = ev.add_source(
        proj.id,
        title="Constitution of India (Tenth Schedule) & Kihoto Hollohan Judgment",
        publisher="Parliament of India / Supreme Court of India",
        source_tier="PRIMARY_OFFICIAL",
        url="https://legislative.gov.in/",
        pub_date="1992-02-18",
    )
    claim_rows = conn.execute(
        "SELECT id, statement FROM claims WHERE project_id = ?", (proj.id,)
    ).fetchall()
    for claim in claim_rows:
        ev.verify_claim_against_source(
            claim_id=claim["id"],
            source_id=src_id,
            page_or_section="Official source excerpt reviewed in test fixture",
            evidence_excerpt=claim["statement"] + " Supporting text inspected in the official source.",
            reviewer_id="e2e-test-reviewer",
        )

    wav_path = tmp_path / "my_narration.wav"
    _write_test_wav(wav_path, duration_sec=4.0)

    res_full = pipeline.run_pipeline(proj.id, voice_path=wav_path)
    assert res_full["status"] == "APPROVED"
    final_mp4 = Path(res_full["render_manifest"]["final_video"])
    assert final_mp4.exists()
    assert final_mp4.stat().st_size > 10000
    assert (proj_dir / "subtitles" / "subtitles.srt").exists()
    assert res_full["qa"]["academic"]["status"] == "PASSED"
    assert res_full["qa"]["rights"]["status"] == "PASSED"
    assert res_full["qa"]["media"]["status"] == "PASSED"
    assert res_full["ten_gates"]["failed_gates"] == []
    assert (proj_dir / "publishing" / "thumbnail.png").exists()
    assert (proj_dir / "publishing" / "publishing_package.json").exists()
    assert (proj_dir / "teaching" / "definitions_and_mindmap.md").exists()
    assert (proj_dir / "teaching" / "duration_schedule.json").exists()
    # Publication gate must remain PENDING until explicit human approval
    assert res_full["qa"]["publication"]["status"] == "PENDING"

    # Explicit human approval unlocks READY_FOR_PUBLICATION
    auditor = QAAuditor(conn, proj_dir)
    approved = auditor.run_all_checks(proj.id, human_approved_by="Creator")
    assert approved["publication"]["status"] == "PASSED"


def test_fastapi_dashboard_and_api(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "web.db", projects_root=tmp_path / "web_projects")
    client = TestClient(app)

    r_home = client.get("/")
    assert r_home.status_code == 200
    assert "UPSC Studio" in r_home.text

    r_hw = client.get("/api/hardware")
    assert r_hw.status_code == 200
    assert r_hw.json()["ffmpeg_path"] is not None

    r_create = client.post(
        "/api/projects",
        json={"name": "Web Test", "chapter_title": "Monetary Policy Committee"},
    )
    assert r_create.status_code == 200
    pid = r_create.json()["id"]

    r_run = client.post(
        f"/api/projects/{pid}/run",
        data={"typed_notes": "RBI Monetary Policy Committee sets repo rate under RBI Act 1934."},
    )
    assert r_run.status_code == 200
    assert r_run.json()["status"] == "WAITING_FOR_RESEARCH_REVIEW"
