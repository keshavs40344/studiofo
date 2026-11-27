"""Render separate vertical Shorts deliverables from already rendered documentary scenes."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from upsc_studio.core.hardware import find_ffmpeg
from upsc_studio.db.schemas import SceneSpec


class ShortsRenderer:
    """Build 9:16 short clips using original scene segments and the matching audio window."""

    MAX_SHORT_SECONDS = 58.0
    MIN_SHORT_SECONDS = 12.0

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = Path(project_dir)
        self.render_dir = self.project_dir / "render"
        self.scene_dir = self.render_dir / "scenes"
        self.short_dir = self.render_dir / "shorts"
        self.short_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def build_candidates(
        cls, scenes: list[SceneSpec], chapter_title: str
    ) -> list[dict[str, Any]]:
        """Greedily group adjacent evidence-linked scenes into self-contained review candidates."""
        candidates: list[dict[str, Any]] = []
        group: list[SceneSpec] = []
        duration = 0.0
        start = 0.0
        timeline_cursor = 0.0
        group_start = 0.0

        def flush() -> None:
            nonlocal group, duration, group_start
            if group and duration >= cls.MIN_SHORT_SECONDS:
                idx = len(candidates) + 1
                source_refs = list(dict.fromkeys(
                    ref for scene in group for ref in scene.source_citations
                ))
                section_names = list(dict.fromkeys(scene.section_title for scene in group))
                candidates.append({
                    "short_id": f"SHORT_{idx:02d}",
                    "title": f"{chapter_title}: {' / '.join(section_names[:2])}"[:100],
                    "scene_ids": [scene.scene_id for scene in group],
                    "start_sec": round(group_start, 3),
                    "duration_sec": round(duration, 3),
                    "source_citations": source_refs,
                    "claim_ids": list(dict.fromkeys(
                        claim for scene in group for claim in scene.claim_ids
                    )),
                    "independently_understandable": False,
                    "human_context_review_required": True,
                })
            group = []
            duration = 0.0

        for scene in scenes:
            scene_duration = max(0.0, float(scene.estimated_duration_sec))
            scene_start = timeline_cursor
            timeline_cursor += scene_duration
            # Do not create standalone factual clips without evidence-linked claims.
            if not scene.claim_ids or scene_duration <= 0:
                if group:
                    flush()
                continue
            if group and duration + scene_duration > cls.MAX_SHORT_SECONDS:
                flush()
            if not group:
                group_start = scene_start
            if scene_duration > cls.MAX_SHORT_SECONDS:
                # A single long scene may be clipped; the original scene remains unchanged.
                scene_duration = cls.MAX_SHORT_SECONDS
            group.append(scene)
            duration += scene_duration
            if duration >= cls.MAX_SHORT_SECONDS:
                flush()
        flush()
        return candidates

    @staticmethod
    def _parse_time(value: str) -> float:
        match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", value.strip())
        if not match:
            raise ValueError(f"Invalid SRT timestamp: {value}")
        hours, minutes, seconds, millis = map(int, match.groups())
        return hours * 3600 + minutes * 60 + seconds + millis / 1000

    @staticmethod
    def _format_time(value: float) -> str:
        millis_total = max(0, int(round(value * 1000)))
        hours, rest = divmod(millis_total, 3_600_000)
        minutes, rest = divmod(rest, 60_000)
        seconds, millis = divmod(rest, 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    @classmethod
    def slice_srt(cls, source_srt: Path, start_sec: float, duration_sec: float, output_srt: Path) -> Path:
        """Keep only cues overlapping the selected audio interval and retime them to zero."""
        raw = source_srt.read_text(encoding="utf-8-sig")
        blocks = re.split(r"\r?\n\s*\r?\n", raw.strip()) if raw.strip() else []
        end_limit = start_sec + duration_sec
        output: list[str] = []
        index = 1
        for block in blocks:
            lines = block.splitlines()
            time_line_idx = next((i for i, line in enumerate(lines) if "-->" in line), None)
            if time_line_idx is None:
                continue
            left, right = [part.strip().split()[0] for part in lines[time_line_idx].split("-->", 1)]
            cue_start, cue_end = cls._parse_time(left), cls._parse_time(right)
            clipped_start = max(start_sec, cue_start)
            clipped_end = min(end_limit, cue_end)
            if clipped_end <= clipped_start:
                continue
            text_lines = lines[time_line_idx + 1:]
            if not text_lines:
                continue
            output.append(
                f"{index}\n{cls._format_time(clipped_start - start_sec)} --> "
                f"{cls._format_time(clipped_end - start_sec)}\n{'\n'.join(text_lines)}"
            )
            index += 1
        output_srt.parent.mkdir(parents=True, exist_ok=True)
        output_srt.write_text("\n\n".join(output) + ("\n" if output else ""), encoding="utf-8")
        return output_srt

    @staticmethod
    def _concat_quote(path: Path) -> str:
        return path.resolve().as_posix().replace("'", "'\\''")

    def render(
        self,
        project_id: str,
        candidates: list[dict[str, Any]],
        scenes: list[SceneSpec],
        narration_wav: Path,
        subtitles_srt: Path,
        preset: str = "veryfast",
        fps: int = 30,
    ) -> dict[str, Any]:
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            return {"status": "FFMPEG_NOT_AVAILABLE", "rendered_count": 0, "shorts": []}
        if not narration_wav.is_file() or not subtitles_srt.is_file():
            raise FileNotFoundError("Shorts rendering requires the final narration and SRT subtitle file.")

        scene_by_id = {scene.scene_id: scene for scene in scenes}
        rendered: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for candidate in candidates:
            short_id = str(candidate.get("short_id") or "")
            scene_ids = candidate.get("scene_ids") or []
            if not short_id or not scene_ids or any(scene_id not in scene_by_id for scene_id in scene_ids):
                errors.append({"short_id": short_id or "UNKNOWN", "error": "Invalid scene selection."})
                continue

            selected = [scene_by_id[scene_id] for scene_id in scene_ids]
            start_sec = float(candidate["start_sec"])
            duration_sec = min(self.MAX_SHORT_SECONDS, float(candidate["duration_sec"]))
            if duration_sec <= 0:
                errors.append({"short_id": short_id, "error": "Non-positive short duration."})
                continue

            vertical_segments: list[Path] = []
            remaining = duration_sec
            try:
                for index, scene in enumerate(selected, start=1):
                    if remaining <= 0:
                        break
                    source = self.scene_dir / f"{scene.scene_id}.mp4"
                    if not source.is_file():
                        raise FileNotFoundError(f"Rendered source scene is missing: {scene.scene_id}")
                    clip_duration = min(float(scene.estimated_duration_sec), remaining)
                    target = self.short_dir / f"{short_id}_scene_{index:02d}.mp4"
                    vf = (
                        "scale=1080:1920:force_original_aspect_ratio=increase,"
                        "crop=1080:1920,fps=30,format=yuv420p"
                    )
                    subprocess.run(
                        [
                            ffmpeg, "-y", "-i", str(source), "-t", f"{clip_duration:.3f}",
                            "-vf", vf, "-an", "-c:v", "libx264", "-preset", preset,
                            "-crf", "24", "-pix_fmt", "yuv420p", str(target),
                        ],
                        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                    )
                    if not target.is_file() or target.stat().st_size == 0:
                        raise RuntimeError(f"FFmpeg did not produce vertical scene {target.name}")
                    vertical_segments.append(target)
                    remaining -= clip_duration

                if not vertical_segments:
                    raise RuntimeError("No vertical scene clips were produced.")
                concat_file = self.short_dir / f"{short_id}_concat.txt"
                concat_file.write_text(
                    "\n".join(f"file '{self._concat_quote(path)}'" for path in vertical_segments),
                    encoding="utf-8",
                )
                silent_video = self.short_dir / f"{short_id}_silent.mp4"
                subprocess.run(
                    [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
                     "-c", "copy", str(silent_video)],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                )

                audio_window = self.short_dir / f"{short_id}_audio.m4a"
                subprocess.run(
                    [ffmpeg, "-y", "-ss", f"{start_sec:.3f}", "-i", str(narration_wav),
                     "-t", f"{duration_sec:.3f}", "-vn", "-c:a", "aac", "-b:a", "128k",
                     str(audio_window)],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                )
                final_video = self.short_dir / f"{short_id}.mp4"
                subprocess.run(
                    [ffmpeg, "-y", "-i", str(silent_video), "-i", str(audio_window),
                     "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy",
                     "-shortest", "-movflags", "+faststart", str(final_video)],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                )
                short_srt = self.short_dir / f"{short_id}.srt"
                self.slice_srt(subtitles_srt, start_sec, duration_sec, short_srt)
                if not final_video.is_file() or final_video.stat().st_size == 0:
                    raise RuntimeError("Final Short MP4 was not created.")
                rendered.append({
                    **candidate,
                    "video_path": str(final_video),
                    "subtitles_path": str(short_srt),
                    "resolution": "1080x1920",
                    "rendered_duration_sec": duration_sec,
                    "status": "RENDERED",
                })
            except (OSError, ValueError, subprocess.CalledProcessError, RuntimeError) as exc:
                errors.append({"short_id": short_id, "error": f"{type(exc).__name__}: {str(exc)[:500]}"})

        report = {
            "project_id": project_id,
            "status": "RENDERED" if rendered and not errors else (
                "PARTIAL" if rendered else ("FAILED" if errors else "NO_ELIGIBLE_SHORTS")
            ),
            "rendered_count": len(rendered),
            "error_count": len(errors),
            "shorts": rendered,
            "errors": errors,
        }
        manifest_path = self.short_dir / "shorts_manifest.json"
        manifest_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report
