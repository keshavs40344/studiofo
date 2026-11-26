"""Phase 15 Real-World Acceptance Run: Fundamental Rights with Piper AI Narration -> Final MP4."""

from __future__ import annotations

import json
import time
from pathlib import Path

import psutil

from upsc_studio.agents.supervisor import ExecutiveProducer
from upsc_studio.core.paths import DEFAULT_DB_PATH, DEFAULT_PROJECTS_DIR
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, VerificationStatus
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.research.verifier import EvidenceEngine


def main() -> None:
    t0 = time.perf_counter()
    conn = init_db(DEFAULT_DB_PATH)
    mgr = ProjectManager(conn, DEFAULT_PROJECTS_DIR)
    proj = mgr.create_project(
        ProjectCreate(
            name="Fundamental Rights AI Factory",
            chapter_title="Fundamental Rights of the Indian Constitution",
            exam_cycle="UPSC CSE 2026",
            cutoff_date="2026-11-26",
            target_duration_min=5,
        )
    )
    proj_dir = Path(proj.root_dir)

    ev = EvidenceEngine(conn, proj_dir)
    const_src = ev.add_source(
        proj.id,
        title="Constitution of India — Part III (Articles 12-35)",
        publisher="Legislative Department, Ministry of Law and Justice",
        source_tier="PRIMARY_OFFICIAL",
        url="https://legislative.gov.in/constitution-of-india/",
        pub_date="2024-05-01",
    )
    ev.add_claim(
        proj.id,
        "Part III (Articles 12-35) guarantees Fundamental Rights enforceable under Article 32.",
        "Constitutional Structure",
        status=VerificationStatus.VERIFIED,
        source_id=const_src,
        page_or_section="Part III, Article 32",
    )

    sup = ExecutiveProducer(conn, DEFAULT_PROJECTS_DIR)
    out = sup.run_autonomous_factory(proj.id, ai_narration=True)

    summary = {
        "project_id": proj.id,
        "status": out["status"],
        "tts_engine": out["audio_report"]["engine"],
        "tts_license": out["audio_report"]["model_license"],
        "narration_full_wav": out["audio_report"]["narration_full_wav"],
        "audio_duration_sec": out["audio_report"]["duration_sec"],
        "final_video": out["render_manifest"]["final_video"],
        "final_video_bytes": out["render_manifest"]["file_size_bytes"],
        "ten_gates": out["ten_gates"]["gates"],
        "youtube_publish": out["youtube_publish"],
        "shorts_count": len(out["editorial_and_shorts"]["shorts_candidates"]),
        "elapsed_sec": round(time.perf_counter() - t0, 2),
        "process_rss_mb": round(psutil.Process().memory_info().rss / (1024 * 1024), 1),
    }
    print(json.dumps(summary, indent=2))
    conn.close()


if __name__ == "__main__":
    main()
