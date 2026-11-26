"""Real-world demonstration runner: Fundamental Rights of the Indian Constitution (no fabricated voice)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import psutil

from upsc_studio.core.hardware import detect_hardware
from upsc_studio.core.paths import DEFAULT_DB_PATH, DEFAULT_PROJECTS_DIR
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, VerificationStatus
from upsc_studio.pipeline.orchestrator import ChapterPipeline
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.research.verifier import EvidenceEngine


def main() -> None:
    t0 = time.perf_counter()
    hw = detect_hardware(DEFAULT_PROJECTS_DIR)
    conn = init_db(DEFAULT_DB_PATH)
    mgr = ProjectManager(conn, DEFAULT_PROJECTS_DIR)

    proj = mgr.create_project(
        ProjectCreate(
            name="Fundamental Rights Demo",
            chapter_title="Fundamental Rights of the Indian Constitution",
            exam_cycle="UPSC CSE 2026",
            cutoff_date="2026-11-26",
            target_duration_min=8,
            tts_enabled=False,
        )
    )
    proj_dir = Path(proj.root_dir)

    # Register official Constitutional sources & verified claims
    ev = EvidenceEngine(conn, proj_dir)
    const_src = ev.add_source(
        proj.id,
        title="Constitution of India — Part III (Articles 12-35)",
        publisher="Legislative Department, Ministry of Law and Justice, Government of India",
        source_tier="PRIMARY_OFFICIAL",
        url="https://legislative.gov.in/constitution-of-india/",
        pub_date="2024-05-01",
    )
    sc_src = ev.add_source(
        proj.id,
        title="K.S. Puttaswamy (Retd.) v. Union of India (2017) 10 SCC 1",
        publisher="Supreme Court of India",
        source_tier="PRIMARY_OFFICIAL",
        url="https://main.sci.gov.in/",
        pub_date="2017-08-24",
    )
    ev.add_claim(
        proj.id,
        "Part III of the Constitution of India (Articles 12 to 35) guarantees six categories of Fundamental Rights.",
        "Constitutional Structure",
        status=VerificationStatus.VERIFIED,
        source_id=const_src,
        page_or_section="Part III, Articles 12-35",
    )
    ev.add_claim(
        proj.id,
        "Article 32 empowers the Supreme Court to issue writs (Habeas Corpus, Mandamus, Prohibition, Certiorari, Quo Warranto) for enforcement of Fundamental Rights.",
        "Constitutional Remedies",
        status=VerificationStatus.VERIFIED,
        source_id=const_src,
        page_or_section="Article 32",
    )
    ev.add_claim(
        proj.id,
        "In K.S. Puttaswamy (2017), a 9-judge bench of the Supreme Court unanimously held Right to Privacy as a Fundamental Right under Article 21.",
        "Judicial Interpretation",
        status=VerificationStatus.VERIFIED,
        source_id=sc_src,
        page_or_section="2017 10 SCC 1",
    )

    notes_text = (
        "Fundamental Rights of the Indian Constitution are enshrined in Part III (Articles 12-35). "
        "They are justiciable rights designed to protect individual liberty against arbitrary State action. "
        "Under Article 32 (described by Dr. B.R. Ambedkar as the heart and soul of the Constitution), citizens can directly move the Supreme Court. "
        "For example, in K.S. Puttaswamy (2017), privacy was affirmed under Article 21. "
        "However, Fundamental Rights are not absolute and are subject to reasonable restrictions under Article 19(2)-(6)."
    )

    pipeline = ChapterPipeline(conn, DEFAULT_PROJECTS_DIR)
    # No user voice recording supplied yet -> must complete all non-voice stages and pause at WAITING_FOR_VOICE
    result = pipeline.run_pipeline(proj.id, typed_notes=notes_text, voice_path=None)

    elapsed = round(time.perf_counter() - t0, 2)
    mem_mb = round(psutil.Process().memory_info().rss / (1024 * 1024), 1)
    dir_bytes = sum(f.stat().st_size for f in proj_dir.rglob("*") if f.is_file())

    summary = {
        "project_id": proj.id,
        "project_dir": str(proj_dir),
        "status": result["status"],
        "specialist_profile": result["specialist_profile"],
        "matched_pyqs": result["matched_pyqs"],
        "scenes_count": result["scenes_count"],
        "duration_schedule": result["duration_schedule"],
        "ten_gates": result["ten_gates"]["gates"],
        "hardware": {
            "cpu": hw.cpu_model,
            "ram_gb": hw.total_ram_gb,
            "free_disk_gb": hw.free_disk_gb,
            "process_rss_mb": mem_mb,
            "elapsed_sec": elapsed,
            "project_size_kb": round(dir_bytes / 1024, 1),
        },
    }
    print(json.dumps(summary, indent=2))
    conn.close()


if __name__ == "__main__":
    main()
