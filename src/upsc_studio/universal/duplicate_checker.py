"""Content Library & Duplicate Explanation Checker: Prevents duplicate video production and identifies exact upgrade deltas."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class OverlapAnalysisResult:
    topic_title: str
    existing_video_id: Optional[str]
    existing_video_title: Optional[str]
    overall_overlap_score: float   # 0.0 to 1.0
    is_duplicate: bool
    already_covered_concepts: list[str] = field(default_factory=list)
    missing_concepts_needed: list[str] = field(default_factory=list)
    outdated_concepts_to_update: list[str] = field(default_factory=list)
    recommended_action: str = "PROCEED_NEW_DOCUMENTARY"   # PROCEED_NEW_DOCUMENTARY, UPDATE_EXISTING, SPLIT_ADVANCED_SERIES

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DuplicateExplanationChecker:
    """Scans existing project repository and catalogue to detect redundant production and plan deltas."""

    def __init__(self, conn: sqlite3.Connection, projects_root: Path) -> None:
        self.conn = conn
        self.projects_root = projects_root

    def check_topic_overlap(
        self,
        new_topic_title: str,
        planned_subtopics: list[str],
        reference_year: int = 2026,
    ) -> OverlapAnalysisResult:
        """Compare planned subtopics against all existing projects and scripts."""
        existing_projects = self._load_existing_project_scripts()
        best_match_proj: Optional[dict[str, Any]] = None
        best_overlap_score = 0.0
        already_covered: list[str] = []
        missing_needed: list[str] = []
        outdated: list[str] = []

        new_title_lower = new_topic_title.lower()
        new_tokens = set(re.findall(r"\w+", new_title_lower)) - {"the", "a", "an", "and", "of", "in", "to", "for"}

        for p in existing_projects:
            p_title_lower = p["chapter_title"].lower()
            p_script_lower = p["script_text"].lower()

            # Title similarity
            p_title_tokens = set(re.findall(r"\w+", p_title_lower))
            title_overlap = len(new_tokens & p_title_tokens) / max(1, len(new_tokens))

            # Subtopic coverage
            covered_in_p: list[str] = []
            for sub in planned_subtopics:
                sub_tokens = set(re.findall(r"\w+", sub.lower())) - {"the", "a", "an", "of"}
                if sub_tokens and all(tok in p_script_lower for tok in list(sub_tokens)[:3]):
                    covered_in_p.append(sub)

            subtopic_overlap = (len(covered_in_p) / len(planned_subtopics)) if planned_subtopics else 0.0
            total_score = (title_overlap * 0.4) + (subtopic_overlap * 0.6)

            if total_score > best_overlap_score:
                best_overlap_score = total_score
                best_match_proj = p
                already_covered = covered_in_p
                missing_needed = [s for s in planned_subtopics if s not in covered_in_p]

                # Check if existing script is outdated (created before 2024)
                if "2020" in p["script_text"] or "2021" in p["script_text"]:
                    outdated = [s for s in covered_in_p if "recent" in s.lower() or "current" in s.lower()]

        is_duplicate = best_overlap_score >= 0.75
        if is_duplicate:
            action = "UPGRADE_EXISTING_VIDEO_DELTA"
        elif best_overlap_score >= 0.45:
            action = "PRODUCE_ADVANCED_COMPANION_LESSON"
        else:
            action = "PROCEED_NEW_DOCUMENTARY"

        return OverlapAnalysisResult(
            topic_title=new_topic_title,
            existing_video_id=best_match_proj["project_id"] if best_match_proj else None,
            existing_video_title=best_match_proj["chapter_title"] if best_match_proj else None,
            overall_overlap_score=round(best_overlap_score, 2),
            is_duplicate=is_duplicate,
            already_covered_concepts=already_covered,
            missing_concepts_needed=missing_needed if best_match_proj else planned_subtopics,
            outdated_concepts_to_update=outdated,
            recommended_action=action,
        )

    def _load_existing_project_scripts(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            rows = self.conn.execute("SELECT id, name, chapter_title, root_dir FROM projects").fetchall()
            for r in rows:
                pdir = Path(r["root_dir"])
                script_path = pdir / "teaching" / "script_hinglish_display.md"
                if not script_path.exists():
                    script_path = pdir / "teaching" / "script_hinglish.md"
                script_text = script_path.read_text(encoding="utf-8") if script_path.exists() else ""
                results.append({
                    "project_id": r["id"],
                    "chapter_title": r["chapter_title"],
                    "script_text": script_text,
                })
        except Exception:
            pass
        return results
