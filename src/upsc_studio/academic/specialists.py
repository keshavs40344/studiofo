"""Subject-specific UPSC GS teaching profiles (GS-I to GS-IV, Prelims, CSAT, Essay, Current Affairs)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from upsc_studio.core.paths import DEFAULT_DATA_DIR


class SpecialistProfileEngine:
    """Selects and applies subject-specific UPSC teaching profiles."""

    def __init__(self, profiles_path: Path | None = None) -> None:
        path = profiles_path or (DEFAULT_DATA_DIR / "gs_profiles.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.version = data["version"]
        self.profiles: dict[str, dict] = data["profiles"]

    def select_profile(self, chapter_title: str, primary_papers: list[str]) -> tuple[str, dict]:
        """Choose the most appropriate specialist profile without confusing CSAT with GS-II."""
        title_l = chapter_title.lower()
        top_paper = primary_papers[0] if primary_papers else ""
        papers_str = " ".join(primary_papers)

        if top_paper == "Prelims CSAT Paper II" or "csat" in title_l:
            return "PRELIMS_CSAT", self.profiles["PRELIMS_CSAT"]
        if "Essay" in top_paper or "essay" in title_l:
            return "ESSAY", self.profiles["ESSAY"]
        if "Mains GS Paper IV" in top_paper or any(k in title_l for k in ("ethics", "integrity", "conflict of interest", "aptitude")):
            return "GS-IV", self.profiles["GS-IV"]
        if any(re.search(rf"\b{k}\b", title_l) for k in ("history", "national movement", "monsoon", "geography", "society", "heritage", "culture")):
            return "GS-I", self.profiles["GS-I"]
        if any(re.search(rf"\b{k}\b", title_l) for k in ("constitution", "fundamental rights", "federalism", "parliament", "anti-defection", "international relations", "governance")):
            return "GS-II", self.profiles["GS-II"]
        if any(re.search(rf"\b{k}\b", title_l) for k in ("economy", "inflation", "monetary", "agriculture", "biodiversity", "security", "disaster")):
            return "GS-III", self.profiles["GS-III"]
        if "Mains GS Paper III" in papers_str:
            return "GS-III", self.profiles["GS-III"]
        if "Mains GS Paper II" in papers_str:
            return "GS-II", self.profiles["GS-II"]
        if "Mains GS Paper I" in papers_str:
            return "GS-I", self.profiles["GS-I"]
        if "Prelims GS Paper I" in papers_str:
            return "PRELIMS_GS1", self.profiles["PRELIMS_GS1"]
        return "CURRENT_AFFAIRS", self.profiles["CURRENT_AFFAIRS"]
