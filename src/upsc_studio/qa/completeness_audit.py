"""Final video element completeness and continuity audit (scene-level + video-wide)."""

from __future__ import annotations

import json
import re
import subprocess
from enum import Enum
from pathlib import Path

from upsc_studio.core.hardware import find_ffmpeg
from upsc_studio.db.schemas import RightsStatus, SceneSpec


class ElementCategory(str, Enum):
    REQUIRED_AND_PRESENT = "REQUIRED_AND_PRESENT"
    REQUIRED_BUT_MISSING = "REQUIRED_BUT_MISSING"
    OPTIONAL_AND_USED = "OPTIONAL_AND_USED"
    OPTIONAL_AND_NOT_NEEDED = "OPTIONAL_AND_NOT_NEEDED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    FAILED_VALIDATION = "FAILED_VALIDATION"


class CompletenessAuditor:
    """Audits scene-level pedagogy/visuals and video-wide technical continuity."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.qa_dir = project_dir / "qa"
        self.qa_dir.mkdir(parents=True, exist_ok=True)

    def audit_video(self, scenes: list[SceneSpec], final_mp4: Path, is_csat_chapter: bool = False) -> dict:
        """Run scene-by-scene completeness audit and FFmpeg blackdetect continuity check."""
        scene_reports: list[dict] = []
        for s in scenes:
            has_asset = bool(s.primary_asset and Path(s.primary_asset).exists())
            has_rights = s.asset_rights_status in {
                RightsStatus.ORIGINAL_GENERATED,
                RightsStatus.USER_OWNED,
                RightsStatus.PUBLIC_DOMAIN,
                RightsStatus.LICENSED,
            }
            scene_reports.append(
                {
                    "scene_id": s.scene_id,
                    "teaching_objective": s.learning_objective,
                    "visual_category": s.visual_category,
                    "asset_present": has_asset,
                    "rights_cleared": has_rights,
                    "duration_sec": s.estimated_duration_sec,
                    "readable_duration": s.estimated_duration_sec >= 3.0,
                    "transition_in": s.transition_in,
                    "transition_out": s.transition_out,
                    "source_citations": s.source_citations,
                    "status": "PASSED" if (has_asset and has_rights and s.learning_objective) else "FAILED",
                }
            )

        black_frames_detected = self._detect_black_frames(final_mp4)

        has_anim = any((s.primary_asset or "").endswith(".mp4") for s in scenes)
        has_map = any("_map.png" in (s.primary_asset or "") for s in scenes)
        has_chart = any("_chart.png" in (s.primary_asset or "") for s in scenes)
        has_split = any("_split.png" in (s.primary_asset or "") for s in scenes)
        has_srt = (self.project_dir / "subtitles" / "subtitles.srt").exists()
        has_otio = (self.project_dir / "render" / "final" / "timeline.otio").exists()

        element_matrix = {
            "learning_objectives": ElementCategory.REQUIRED_AND_PRESENT.value
            if (self.project_dir / "syllabus" / "learning_objectives.md").exists()
            else ElementCategory.REQUIRED_BUT_MISSING.value,
            "hinglish_script_and_recording_prompt": ElementCategory.REQUIRED_AND_PRESENT.value
            if (self.project_dir / "teaching" / "script_hinglish.md").exists()
            else ElementCategory.REQUIRED_BUT_MISSING.value,
            "animated_constitutional_or_process_visual": ElementCategory.OPTIONAL_AND_USED.value
            if has_anim
            else ElementCategory.OPTIONAL_AND_NOT_NEEDED.value,
            "institutional_or_geographical_map": ElementCategory.OPTIONAL_AND_USED.value
            if has_map
            else ElementCategory.OPTIONAL_AND_NOT_NEEDED.value,
            "source_cited_data_chart": ElementCategory.OPTIONAL_AND_USED.value
            if has_chart
            else ElementCategory.OPTIONAL_AND_NOT_NEEDED.value,
            "split_screen_comparison": ElementCategory.OPTIONAL_AND_USED.value
            if has_split
            else ElementCategory.OPTIONAL_AND_NOT_NEEDED.value,
            "synchronized_subtitles_srt": ElementCategory.REQUIRED_AND_PRESENT.value
            if has_srt
            else ElementCategory.REQUIRED_BUT_MISSING.value,
            "otio_interchange_timeline": ElementCategory.OPTIONAL_AND_USED.value
            if has_otio
            else ElementCategory.OPTIONAL_AND_NOT_NEEDED.value,
            "csat_problem_solving_animation": ElementCategory.OPTIONAL_AND_NOT_NEEDED.value
            if is_csat_chapter
            else ElementCategory.NOT_APPLICABLE.value,
            "zero_unintended_black_frames": ElementCategory.REQUIRED_AND_PRESENT.value
            if black_frames_detected == 0
            else ElementCategory.FAILED_VALIDATION.value,
        }

        report = {
            "scenes_audited": len(scene_reports),
            "black_frame_segments_detected": black_frames_detected,
            "element_matrix": element_matrix,
            "scenes": scene_reports,
        }
        (self.qa_dir / "completeness_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    @staticmethod
    def _detect_black_frames(video_path: Path) -> int:
        """Run FFmpeg blackdetect to catch unintended black frames."""
        if not video_path.exists():
            return -1
        ffmpeg_exe = find_ffmpeg()
        if not ffmpeg_exe:
            return -1
        proc = subprocess.run(
            [ffmpeg_exe, "-i", str(video_path), "-vf", "blackdetect=d=0.5:pix_th=0.10", "-f", "null", "-"],
            capture_output=True,
            text=True,
        )
        matches = re.findall(r"black_start:", proc.stderr or "")
        return len(matches)
