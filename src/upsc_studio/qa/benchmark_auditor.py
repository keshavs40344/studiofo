"""Golden Test Chapter Library benchmark runner and measurable academic acceptance auditor."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from upsc_studio.academic.mains_analyzer import MainsAnswerAnalyzer
from upsc_studio.academic.pyq_engine import PYQEngine
from upsc_studio.academic.specialists import SpecialistProfileEngine
from upsc_studio.core.paths import DEFAULT_DATA_DIR
from upsc_studio.db.schemas import ProjectCreate
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.research.verifier import EvidenceEngine
from upsc_studio.storyboard.adaptive_visuals import AdaptiveVisualSelector
from upsc_studio.syllabus.engine import SyllabusEngine
from upsc_studio.teaching.engine import TeachingEngine


class BenchmarkAuditor:
    """Evaluates all 10 Golden Test Chapters and reports passed/failed/pending/human-review checks."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        projects_root: Path,
        golden_path: Path | None = None,
    ) -> None:
        self.conn = conn
        self.projects_root = projects_root
        path = golden_path or (DEFAULT_DATA_DIR / "golden_chapters.json")
        self.benchmarks: list[dict] = json.loads(path.read_text(encoding="utf-8"))["chapters"]
        self.mgr = ProjectManager(conn, projects_root)
        self.syllabus = SyllabusEngine(conn)
        self.specialists = SpecialistProfileEngine()
        self.pyq = PYQEngine()
        self.mains = MainsAnswerAnalyzer()

    def run_all_benchmarks(self) -> dict:
        """Execute academic, syllabus, PYQ, visual, and teaching audits across all 10 golden chapters."""
        results: list[dict] = []
        summary = {"PASSED": 0, "FAILED": 0, "PENDING": 0, "HUMAN_REVIEW_REQUIRED": 0}

        for bm in self.benchmarks:
            proj = self.mgr.create_project(ProjectCreate(name=bm["id"], chapter_title=bm["title"]))
            proj_dir = Path(proj.root_dir)
            cmap = self.syllabus.map_chapter(proj.id, proj_dir, bm["title"], notes_text=bm["sample_notes"])

            mapped_papers = {
                e["paper"] for e in (cmap["prelims_dimensions"] + cmap["mains_dimensions"])
            }
            specialist_key, profile = self.specialists.select_profile(bm["title"], list(mapped_papers))

            # Checks
            forbidden_hit = any(fp in mapped_papers for fp in bm["forbidden_papers"])
            expected_hit = any(ep in mapped_papers for ep in bm["expected_papers"])
            syllabus_ok = expected_hit and not forbidden_hit and specialist_key == bm["expected_specialist"]

            ev = EvidenceEngine(self.conn, proj_dir)
            src_id = ev.add_source(proj.id, f"Notes for {bm['title']}", "Benchmark Corpus", "USER_NOTES")
            ev.extract_claims_from_text(proj.id, "Notes", bm["sample_notes"], default_source_id=src_id)
            ledger = ev.export_ledger(proj.id, "2026-11-26")

            teach = TeachingEngine(self.conn, proj_dir).generate_teaching_package(
                proj.id, bm["title"], cmap, notes_excerpt=bm["sample_notes"]
            )
            qbank = json.loads((proj_dir / "teaching" / "question_bank.json").read_text(encoding="utf-8"))
            pyq_errors = self.pyq.validate_question_bank_authenticity(qbank)
            matched_pyqs = self.pyq.match_chapter(bm["title"])
            mains_fw = self.mains.build_framework(
                f"Critically examine {bm['title']}.", bm["title"], profile
            )
            visual_choice = AdaptiveVisualSelector.choose_visual(specialist_key, "mechanism", bm["title"])

            checks = {
                "syllabus_mapping_audit": "PASSED" if syllabus_ok else "FAILED",
                "pyq_authenticity_audit": "PASSED" if not pyq_errors else "FAILED",
                "teaching_and_mains_framework": "PASSED" if (teach["sections_count"] >= 5 and mains_fw["directive_word"] == "CRITICALLY EXAMINE") else "FAILED",
                "adaptive_visual_selection": "PASSED" if bool(visual_choice) else "FAILED",
                "fact_verification_audit": "HUMAN_REVIEW_REQUIRED" if ledger["status_counts"]["HUMAN_REVIEW_REQUIRED"] > 0 or ledger["status_counts"]["UNSUPPORTED"] > 0 else "PASSED",
                "voice_and_video_render": "PENDING",
            }
            for st in checks.values():
                summary[st] = summary.get(st, 0) + 1

            results.append(
                {
                    "benchmark_id": bm["id"],
                    "title": bm["title"],
                    "specialist_selected": specialist_key,
                    "mapped_papers": sorted(mapped_papers),
                    "matched_pyqs_count": len(matched_pyqs),
                    "visual_selected": visual_choice,
                    "checks": checks,
                }
            )

        return {"total_benchmarks": len(results), "check_counts": summary, "benchmarks": results}
