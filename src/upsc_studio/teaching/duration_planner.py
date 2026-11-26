"""Video duration schedule planner with multi-part proposal when syllabus exceeds target duration."""

from __future__ import annotations

import json
from pathlib import Path


class DurationPlanner:
    """Calculates realistic narration + visual schedule without speeding up user's voice."""

    def __init__(self, words_per_minute: float = 130.0) -> None:
        self.words_per_minute = words_per_minute

    def build_schedule(
        self,
        project_dir: Path,
        sections: list[dict],
        target_duration_min: int,
        actual_rendered_sec: float | None = None,
    ) -> dict:
        """Compute planned duration, check against target, and propose multi-part split if needed."""
        total_words = sum(len(s["narration"].split()) for s in sections)
        planned_sec = sum(float(s["duration_sec"]) for s in sections)
        planned_min = round(planned_sec / 60.0, 2)
        target_sec = target_duration_min * 60.0

        exceeds_target = planned_sec > (target_sec * 1.15)
        parts_proposal: list[dict] = []
        if exceeds_target:
            half = max(1, len(sections) // 2)
            parts_proposal = [
                {"part": 1, "sections": [s["section_id"] for s in sections[:half]]},
                {"part": 2, "sections": [s["section_id"] for s in sections[half:]]},
            ]

        schedule = {
            "target_duration_min": target_duration_min,
            "measured_wpm": self.words_per_minute,
            "total_words": total_words,
            "planned_duration_sec": round(planned_sec, 2),
            "planned_duration_min": planned_min,
            "actual_rendered_duration_sec": round(actual_rendered_sec, 2) if actual_rendered_sec is not None else None,
            "actual_rendered_duration_min": round(actual_rendered_sec / 60.0, 2) if actual_rendered_sec is not None else None,
            "voice_speedup_applied": False,
            "status": "MULTI_PART_RECOMMENDED" if exceeds_target else "FITS_TARGET_DURATION",
            "multi_part_proposal": parts_proposal,
        }
        (project_dir / "teaching" / "duration_schedule.json").write_text(
            json.dumps(schedule, indent=2), encoding="utf-8"
        )
        return schedule
