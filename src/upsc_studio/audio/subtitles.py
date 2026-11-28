"""High-precision educational subtitle alignment, line-splitting, and drift inspection."""

from __future__ import annotations

import re
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from upsc_studio.db.schemas import SceneSpec


@dataclass
class SubtitleCue:
    index: int
    start_sec: float
    end_sec: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubtitleQAInspection:
    total_cues: int
    total_duration_sec: float
    has_overlaps: bool
    has_negative_durations: bool
    has_excessive_reading_speed: bool
    max_reading_speed_cps: float
    is_valid: bool
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SubtitleEngine:
    """Produces readable, well-paced SRT and WebVTT subtitles conforming to broadcast specs."""

    MAX_LINE_CHARS = 42              # Optimal subtitle readability width
    MAX_LINES_PER_CUE = 2            # Maximum 2 lines per subtitle cue
    MIN_CUE_DURATION = 1.0           # Minimum duration on screen
    MAX_CUE_DURATION = 7.0           # Maximum duration on screen
    MAX_READING_SPEED_CPS = 21.0     # Maximum characters per second for comfortable comprehension

    @staticmethod
    def _format_srt_timestamp(seconds: float) -> str:
        ms = int(round((seconds - int(seconds)) * 1000))
        total_sec = int(seconds)
        hours = total_sec // 3600
        mins = (total_sec % 3600) // 60
        secs = total_sec % 60
        return f"{hours:02d}:{mins:02d}:{secs:02d},{ms:03d}"

    @staticmethod
    def _format_vtt_timestamp(seconds: float) -> str:
        ms = int(round((seconds - int(seconds)) * 1000))
        total_sec = int(seconds)
        hours = total_sec // 3600
        mins = (total_sec % 3600) // 60
        secs = total_sec % 60
        return f"{hours:02d}:{mins:02d}:{secs:02d}.{ms:03d}"

    def split_into_readable_lines(self, sentence: str) -> str:
        """Split a long sentence into at most 2 balanced lines of at most 42 characters each."""
        clean = " ".join(sentence.split())
        if len(clean) <= self.MAX_LINE_CHARS:
            return clean

        lines = textwrap.wrap(clean, width=self.MAX_LINE_CHARS)
        return "\n".join(lines[: self.MAX_LINES_PER_CUE])

    def align_scenes_to_cues(
        self,
        scenes: list[SceneSpec],
        actual_audio_duration_sec: Optional[float] = None,
    ) -> list[SubtitleCue]:
        """Distribute scene narration text into proportional, drift-free subtitle cues."""
        est_total = sum(s.estimated_duration_sec for s in scenes) or 1.0
        scale = (actual_audio_duration_sec / est_total) if (actual_audio_duration_sec and actual_audio_duration_sec > 0) else 1.0

        cues: list[SubtitleCue] = []
        cursor = 0.0
        cue_idx = 1

        for scene in scenes:
            scene_duration = max(1.2, scene.estimated_duration_sec * scale)
            # Break narration into atomic sentence units
            raw_sentences = [
                s.strip()
                for s in re.split(r"(?<=[.!?।])\s+", scene.narration_text)
                if len(s.strip()) >= 5
            ]
            if not raw_sentences:
                raw_sentences = [scene.on_screen_title]

            total_chars = sum(len(s) for s in raw_sentences) or 1
            for sent in raw_sentences:
                proportional_dur = scene_duration * (len(sent) / total_chars)
                clamped_dur = max(self.MIN_CUE_DURATION, min(self.MAX_CUE_DURATION, proportional_dur))

                start = cursor
                end = cursor + clamped_dur

                formatted_text = self.split_into_readable_lines(sent)
                cues.append(
                    SubtitleCue(
                        index=cue_idx,
                        start_sec=round(start, 3),
                        end_sec=round(end, 3),
                        text=formatted_text,
                    )
                )
                cue_idx += 1
                cursor = end + 0.05  # 50ms gap between consecutive cues

        return cues

    def write_srt(self, cues: list[SubtitleCue], out_path: Path) -> Path:
        """Write cues to standard SRT subtitle format."""
        out_path.parent.mkdir(parents=True, exist_ok=True)
        blocks = []
        for c in cues:
            start_str = self._format_srt_timestamp(c.start_sec)
            end_str = self._format_srt_timestamp(c.end_sec)
            blocks.append(f"{c.index}\n{start_str} --> {end_str}\n{c.text}\n")

        out_path.write_text("\n".join(blocks), encoding="utf-8")
        return out_path

    def write_vtt(self, cues: list[SubtitleCue], out_path: Path) -> Path:
        """Write cues to WebVTT format."""
        out_path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["WEBVTT\n"]
        for c in cues:
            start_str = self._format_vtt_timestamp(c.start_sec)
            end_str = self._format_vtt_timestamp(c.end_sec)
            lines.append(f"{c.index}\n{start_str} --> {end_str}\n{c.text}\n")

        out_path.write_text("\n".join(lines), encoding="utf-8")
        return out_path

    def inspect_cues_quality(self, cues: list[SubtitleCue]) -> SubtitleQAInspection:
        """Validate subtitle timing, absence of overlaps, and comfortable reading speeds."""
        issues: list[str] = []
        has_overlaps = False
        has_negative_dur = False
        max_speed = 0.0

        for idx, cue in enumerate(cues):
            duration = cue.end_sec - cue.start_sec
            if duration <= 0:
                has_negative_dur = True
                issues.append(f"Cue #{cue.index} has non-positive duration ({duration}s).")

            # Check overlap with subsequent cue
            if idx < len(cues) - 1:
                next_cue = cues[idx + 1]
                if cue.end_sec > next_cue.start_sec:
                    has_overlaps = True
                    issues.append(f"Overlap detected: Cue #{cue.index} ({cue.end_sec}s) exceeds start of Cue #{next_cue.index} ({next_cue.start_sec}s).")

            # Check reading speed in characters per second
            clean_text = cue.text.replace("\n", "")
            cps = len(clean_text) / duration if duration > 0 else 0.0
            if cps > max_speed:
                max_speed = cps
            if cps > self.MAX_READING_SPEED_CPS:
                issues.append(f"Cue #{cue.index} reading speed ({cps:.1f} chars/sec) exceeds comfortable threshold ({self.MAX_READING_SPEED_CPS} chars/sec).")

        total_dur = cues[-1].end_sec if cues else 0.0
        is_valid = not (has_overlaps or has_negative_dur)

        return SubtitleQAInspection(
            total_cues=len(cues),
            total_duration_sec=round(total_dur, 2),
            has_overlaps=has_overlaps,
            has_negative_durations=has_negative_dur,
            has_excessive_reading_speed=max_speed > self.MAX_READING_SPEED_CPS,
            max_reading_speed_cps=round(max_speed, 1),
            is_valid=is_valid,
            issues=issues,
        )
