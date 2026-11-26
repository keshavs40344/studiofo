"""Authentic UPSC Previous Year Question (PYQ) matching and authenticity enforcement."""

from __future__ import annotations

import json
from pathlib import Path

from upsc_studio.core.paths import DEFAULT_DATA_DIR


class PYQEngine:
    """Matches authentic UPSC PYQs to chapters and prevents mislabelling practice items."""

    def __init__(self, pyq_path: Path | None = None) -> None:
        path = pyq_path or (DEFAULT_DATA_DIR / "pyq_bank.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.version = data["version"]
        self.pyqs: list[dict] = data["pyqs"]

    def match_chapter(self, chapter_title: str, syllabus_ids: list[str] | None = None) -> list[dict]:
        """Return authentic PYQs matching the chapter title or syllabus item IDs."""
        title_l = chapter_title.lower()
        sid_set = set(syllabus_ids or [])
        matched: list[dict] = []
        for q in self.pyqs:
            tag_hit = any(t in title_l for t in q.get("topic_tags", []))
            sid_hit = q.get("syllabus_item_id") in sid_set
            if tag_hit or sid_hit:
                matched.append(q)
        return matched

    @staticmethod
    def validate_question_bank_authenticity(question_bank: dict) -> list[str]:
        """Verify no generated practice item is labelled as an official UPSC PYQ."""
        errors: list[str] = []
        for group_key in ("prelims_practice_mcqs", "mains_practice_questions"):
            for item in question_bank.get(group_key, []):
                if item.get("label") != "PRACTICE_GENERATED":
                    errors.append(f"{item.get('id', 'unknown')} in {group_key} lacks PRACTICE_GENERATED label.")
        for pyq in question_bank.get("verified_pyqs", []):
            if not pyq.get("official_source") or not pyq.get("year"):
                errors.append(f"PYQ {pyq.get('id', 'unknown')} is missing official_source or year.")
        return errors
