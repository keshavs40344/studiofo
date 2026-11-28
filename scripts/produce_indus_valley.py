"""End-to-end production runner for the Indus Valley Civilization documentary."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from upsc_studio.core.paths import PROJECT_ROOT
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, VerificationStatus
from upsc_studio.pipeline.monitoring import RuntimeMonitor
from upsc_studio.pipeline.staged import StagedChapterPipeline
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.qa.release_audit import ReleaseAuditGenerator
from upsc_studio.research.verifier import EvidenceEngine


def main() -> None:
    t_start = time.perf_counter()
    os.environ["UPSC_STUDIO_AUTO_RESEARCH"] = "0"

    pack_path = PROJECT_ROOT / "data" / "knowledge_packs" / "indus_valley_civilization.json"
    pack = json.loads(pack_path.read_text(encoding="utf-8"))

    db_path = PROJECT_ROOT / "data" / "indus_valley_production.db"
    projects_root = PROJECT_ROOT / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)

    conn = init_db(db_path)
    mgr = ProjectManager(conn, projects_root)

    # Reuse existing project if already created, else create fresh
    existing = [p for p in mgr.list_projects() if p.chapter_title == pack["chapter_title"]]
    if existing:
        project = existing[0]
    else:
        project = mgr.create_project(
            ProjectCreate(
                name=pack["project_name"],
                chapter_title=pack["chapter_title"],
                content_category=pack["content_category"],
                exam_cycle=pack["exam_cycle"],
                target_duration_min=pack["target_duration_min"],
                tts_enabled=True,
            )
        )

    project_dir = Path(project.root_dir)
    evidence = EvidenceEngine(conn, project_dir)

    # Clear previous claims/sources if re-running cleanly
    conn.execute("DELETE FROM claims WHERE project_id = ?", (project.id,))
    conn.execute("DELETE FROM sources WHERE project_id = ?", (project.id,))
    conn.commit()

    source_map: dict[str, str] = {}
    for src in pack["sources"]:
        sid = evidence.add_source(
            project_id=project.id,
            title=src["title"],
            publisher=src["publisher"],
            source_tier=src["source_tier"],
            url=src["url"],
            pub_date=src["pub_date"],
        )
        source_map[src["key"]] = sid

    for clm in pack["claims"]:
        evidence.add_claim(
            project_id=project.id,
            statement=clm["statement"],
            chapter_section=clm["section"],
            status=VerificationStatus.VERIFIED,
            source_id=source_map[clm["source_key"]],
            page_or_section=clm["page_or_section"],
        )

    typed_notes = (
        "# Indus Valley Civilization — Complete UPSC Syllabus Notes\n"
        "Covers Early, Mature, and Late Harappan phases, town planning, grid streets, "
        "Great Bath, Dholavira water reservoirs, Lothal dockyard, Kalibangan ploughed field, "
        "agriculture, cotton, standardized chert weights, Mesopotamian trade (Meluhha), "
        "undeciphered boustrophedon script, Pashupati seal, and multi-causal decline."
    )

    pipeline = StagedChapterPipeline(conn, projects_root)
    result = pipeline.run_staged(
        project_id=project.id,
        typed_notes=typed_notes,
        voice_path=None,
        ai_narration=True,
    )

    audit = ReleaseAuditGenerator(conn, project_dir).generate(project.id)
    ops = RuntimeMonitor(conn, projects_root).get_live_project_status(project.id)

    elapsed = round(time.perf_counter() - t_start, 2)
    summary = {
        "project_id": project.id,
        "project_dir": str(project_dir),
        "elapsed_sec": elapsed,
        "pipeline_status": result.get("status"),
        "final_video": ops.get("final_video"),
        "release_candidate_json": audit["release_candidate_json"],
        "release_report_md": audit["release_report_md"],
        "core_gates": audit["candidate"]["core_gates"],
        "research_summary": ops.get("research_summary"),
        "stages": [
            {"stage": s["stage"], "status": s["status"], "duration_sec": s["duration_sec"]}
            for s in ops.get("stages", [])
        ],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
