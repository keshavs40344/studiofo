"""Video duration schedule planner with tolerance, section-level accounting, and multi-part proposals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


class DurationPlanner:
    """Calculates realistic narration + visual schedule without speeding up user's voice.
    
    Enforces tolerance limits:
    - Target duration is checked with min/max bounds (e.g. 0.85x to 1.15x).
    - If narration is under-duration (< 0.70x target), flags INSUFFICIENT_DURATION.
    - If planned exceeds max tolerance (> 1.15x target), proposes multi-part split.
    - Compares actual rendered audio duration against target.
    """

    MIN_TOLERANCE_RATIO = 0.80   # Minimum acceptable fraction of target duration
    MAX_TOLERANCE_RATIO = 1.15   # Maximum acceptable fraction of target duration before multi-part
    UNDER_DURATION_THRESHOLD = 0.70  # Below this is strictly under-duration / insufficient content

    def __init__(self, words_per_minute: float = 130.0) -> None:
        self.words_per_minute = words_per_minute

    def build_schedule(
        self,
        project_dir: Path,
        sections: list[dict[str, Any]],
        target_duration_min: int,
        actual_rendered_sec: float | None = None,
    ) -> dict[str, Any]:
        """Compute planned duration, check against target with tolerances, and propose multi-part split if needed."""
        total_words = sum(len(s.get("narration", "").split()) for s in sections)
        planned_sec = sum(float(s.get("duration_sec", 0.0)) for s in sections)
        planned_min = round(planned_sec / 60.0, 2)
        target_sec = float(target_duration_min * 60.0)

        min_acceptable_sec = target_sec * self.MIN_TOLERANCE_RATIO
        max_acceptable_sec = target_sec * self.MAX_TOLERANCE_RATIO

        # Section-level metrics
        section_breakdowns: list[dict[str, Any]] = []
        for s in sections:
            w_count = len(s.get("narration", "").split())
            sec_dur = float(s.get("duration_sec", 0.0))
            section_breakdowns.append({
                "section_id": s.get("section_id"),
                "title": s.get("title"),
                "word_count": w_count,
                "duration_sec": round(sec_dur, 2),
                "visual_category": s.get("visual_category", "slide"),
            })

        # Evaluate status
        is_under_duration = planned_sec < (target_sec * self.UNDER_DURATION_THRESHOLD)
        exceeds_target = planned_sec > max_acceptable_sec
        fits_target = min_acceptable_sec <= planned_sec <= max_acceptable_sec

        parts_proposal: list[dict[str, Any]] = []
        if exceeds_target:
            half = max(1, len(sections) // 2)
            parts_proposal = [
                {
                    "part": 1,
                    "target_duration_min": round(target_duration_min / 2.0, 1),
                    "sections": [s["section_id"] for s in sections[:half]],
                    "planned_duration_sec": round(sum(float(s.get("duration_sec", 0.0)) for s in sections[:half]), 2),
                },
                {
                    "part": 2,
                    "target_duration_min": round(target_duration_min / 2.0, 1),
                    "sections": [s["section_id"] for s in sections[half:]],
                    "planned_duration_sec": round(sum(float(s.get("duration_sec", 0.0)) for s in sections[half:]), 2),
                },
            ]

        status = "FITS_TARGET_DURATION"
        if is_under_duration:
            status = "INSUFFICIENT_DURATION"
        elif exceeds_target:
            status = "MULTI_PART_RECOMMENDED"

        # Compare actual rendered if present
        rendered_mismatch = False
        actual_min = None
        if actual_rendered_sec is not None:
            actual_min = round(actual_rendered_sec / 60.0, 2)
            if actual_rendered_sec < (target_sec * self.UNDER_DURATION_THRESHOLD):
                rendered_mismatch = True

        schedule = {
            "target_duration_min": target_duration_min,
            "target_duration_sec": target_sec,
            "min_acceptable_sec": round(min_acceptable_sec, 2),
            "max_acceptable_sec": round(max_acceptable_sec, 2),
            "measured_wpm": self.words_per_minute,
            "total_words": total_words,
            "planned_duration_sec": round(planned_sec, 2),
            "planned_duration_min": planned_min,
            "actual_rendered_duration_sec": round(actual_rendered_sec, 2) if actual_rendered_sec is not None else None,
            "actual_rendered_duration_min": actual_min,
            "rendered_mismatch": rendered_mismatch,
            "voice_speedup_applied": False,
            "status": status,
            "multi_part_proposal": parts_proposal,
            "sections": section_breakdowns,
        }

        out_path = project_dir / "teaching" / "duration_schedule.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(schedule, indent=2), encoding="utf-8")
        return schedule
