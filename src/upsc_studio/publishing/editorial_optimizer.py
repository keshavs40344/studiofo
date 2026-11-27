"""Editorial retention scoring, title-thumbnail evaluation, SEO packaging, and Shorts extraction."""

from __future__ import annotations

import json
from pathlib import Path

from upsc_studio.db.schemas import SceneSpec
from upsc_studio.video.shorts import ShortsRenderer


class EditorialOptimizer:
    """Evaluates documentary retention hooks, title-thumbnail concepts, and Shorts candidates."""

    def optimize_and_extract_shorts(
        self,
        project_dir: Path,
        chapter_title: str,
        primary_papers: list[str],
        scenes: list[SceneSpec],
        content_category: str = "upsc",
    ) -> dict:
        category_label = {
            "upsc": "UPSC GS Analysis",
            "general_knowledge": "General Knowledge",
            "current_affairs": "Current Affairs",
            "deep_dive": "Deep Dive",
        }.get(content_category, "Educational Documentary")
        title_candidates = [
            {
                "title": f"{chapter_title} | {category_label}",
                "scores": {"accuracy": None, "readability": None, "relevance": None,
                           "curiosity": None, "clickbait_risk": "REQUIRES_HUMAN_REVIEW"},
            },
            {
                "title": f"Understanding {chapter_title}: Key Evidence and Implications",
                "scores": {"accuracy": None, "readability": None, "relevance": None,
                           "curiosity": None, "clickbait_risk": "REQUIRES_HUMAN_REVIEW"},
            },
        ]

        shorts_candidates = ShortsRenderer.build_candidates(scenes, chapter_title)

        report = {
            "chapter_title": chapter_title,
            "content_category": content_category,
            "retention_structure": [
                "0-20s: Truthful conceptual hook & UPSC stakes",
                "Context -> Mechanism -> Case Studies -> Reforms -> Recap",
            ],
            "title_candidates": title_candidates,
            "seo_hashtags": ["#Education", "#Learning", "#Documentary"],
            "shorts_candidates": shorts_candidates,
        }
        pub_dir = project_dir / "publishing"
        pub_dir.mkdir(parents=True, exist_ok=True)
        (pub_dir / "editorial_and_shorts_plan.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return report
