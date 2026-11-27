"""Audio-Aware Multilingual Subtitle Synchronizer (SRT and WebVTT)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class AudioAwareSubtitleSynchronizer:
    """Aligns sentence-level translations with measured audio durations and generates SRT & WebVTT."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir

    def generate_subtitles(
        self,
        sentences: list[str],
        total_audio_sec: float,
        out_srt: Path,
        out_vtt: Optional[Path] = None,
        lang_code: str = "en",
    ) -> dict[str, Any]:
        """Produce synchronized SRT and WebVTT tracks using audio timing."""
        out_srt.parent.mkdir(parents=True, exist_ok=True)
        if out_vtt:
            out_vtt.parent.mkdir(parents=True, exist_ok=True)

        if not sentences:
            sentences = ["UPSC Studio Documentary"]

        total_chars = sum(len(s) for s in sentences) or 1
        cursor = 0.0

        srt_blocks: list[str] = []
        vtt_blocks: list[str] = ["WEBVTT", f"NOTE Language: {lang_code}", ""]
        segments_meta: list[dict[str, Any]] = []

        for idx, sent in enumerate(sentences, start=1):
            char_ratio = len(sent) / total_chars
            seg_dur = max(1.2, total_audio_sec * char_ratio)
            start_sec = cursor
            end_sec = min(total_audio_sec, cursor + seg_dur)
            cursor = end_sec

            # SRT block
            srt_blocks.append(
                f"{idx}\n{self._fmt_srt_time(start_sec)} --> {self._fmt_srt_time(end_sec)}\n{sent}\n"
            )

            # WebVTT block
            vtt_blocks.append(
                f"{idx}\n{self._fmt_vtt_time(start_sec)} --> {self._fmt_vtt_time(end_sec)}\n{sent}\n"
            )

            segments_meta.append({
                "index": idx,
                "start_sec": round(start_sec, 3),
                "end_sec": round(end_sec, 3),
                "text": sent,
            })

        out_srt.write_text("\n".join(srt_blocks), encoding="utf-8")
        if out_vtt:
            out_vtt.write_text("\n".join(vtt_blocks), encoding="utf-8")

        return {
            "language": lang_code,
            "total_segments": len(sentences),
            "total_duration_sec": round(total_audio_sec, 2),
            "srt_path": str(out_srt),
            "vtt_path": str(out_vtt) if out_vtt else None,
            "segments": segments_meta,
        }

    @staticmethod
    def _fmt_srt_time(seconds: float) -> str:
        ms = int(round(seconds * 1000))
        hrs, rem = divmod(ms, 3600000)
        mins, rem = divmod(rem, 60000)
        secs, ms = divmod(rem, 1000)
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"

    @staticmethod
    def _fmt_vtt_time(seconds: float) -> str:
        ms = int(round(seconds * 1000))
        hrs, rem = divmod(ms, 3600000)
        mins, rem = divmod(rem, 60000)
        secs, ms = divmod(rem, 1000)
        return f"{hrs:02d}:{mins:02d}:{secs:02d}.{ms:03d}"
