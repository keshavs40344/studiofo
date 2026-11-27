"""Resumable scene-wise FFmpeg video timeline assembler, transitions, chapters, and OTIO exporter."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import uuid
from pathlib import Path

from upsc_studio.core.hardware import check_disk_space_ok, find_ffmpeg
from upsc_studio.core.paths import sha256_file
from upsc_studio.db.schemas import SceneSpec, utc_now_iso
from upsc_studio.integrations.otio_exporter import export_otio_timeline


class VideoRenderer:
    """Builds editable timelines (JSON + OTIO) and renders scenes incrementally via FFmpeg."""

    def __init__(self, conn: sqlite3.Connection, project_dir: Path) -> None:
        self.conn = conn
        self.project_dir = project_dir
        self.scenes_dir = project_dir / "render" / "scenes"
        self.final_dir = project_dir / "render" / "final"
        self.scenes_dir.mkdir(parents=True, exist_ok=True)
        self.final_dir.mkdir(parents=True, exist_ok=True)

    def render_project(
        self,
        project_id: str,
        scenes: list[SceneSpec],
        narration_wav: Path,
        subtitles_srt: Path | None = None,
        preset: str = "veryfast",
        fps: int = 30,
        resolution: str = "1920x1080",
        enable_transitions: bool = False,
    ) -> dict:
        """Render cached per-scene segments (PNG or MP4), apply transitions/chapters, and mux narration."""
        ok_disk, free_gb = check_disk_space_ok(self.project_dir, min_free_gb=1.0)
        if not ok_disk:
            raise RuntimeError(f"Insufficient disk space for rendering: {free_gb} GB free.")

        ffmpeg_exe = find_ffmpeg()
        if not ffmpeg_exe:
            raise RuntimeError("FFmpeg executable not found.")
        if not narration_wav.exists():
            raise FileNotFoundError(f"Processed narration WAV not found: {narration_wav}")

        width, height = (int(x) for x in resolution.lower().split("x"))
        rendered_segments: list[Path] = []
        timeline_entries: list[dict] = []

        for scene in scenes:
            if not scene.primary_asset or not Path(scene.primary_asset).exists():
                raise FileNotFoundError(f"Missing primary graphic asset for {scene.scene_id}: {scene.primary_asset}")

            asset_path = Path(scene.primary_asset)
            is_video_asset = asset_path.suffix.lower() in {".mp4", ".mov", ".mkv"}
            input_hash = hashlib.sha256(
                f"{sha256_file(asset_path)}|{scene.estimated_duration_sec}|{preset}|{fps}|{resolution}".encode("utf-8")
            ).hexdigest()

            seg_path = self.scenes_dir / f"{scene.scene_id}.mp4"
            if not self._is_cached(project_id, scene.scene_id, input_hash, seg_path):
                vf_chain = (
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                    f"eq=contrast=1.02:saturation=1.03,format=yuv420p"
                )
                cmd = [ffmpeg_exe, "-y"]
                if not is_video_asset:
                    cmd.extend(["-loop", "1"])
                cmd.extend(
                    [
                        "-i",
                        str(asset_path),
                        "-t",
                        f"{scene.estimated_duration_sec:.2f}",
                        "-vf",
                        vf_chain,
                        "-r",
                        str(fps),
                        "-c:v",
                        "libx264",
                        "-preset",
                        preset,
                        "-crf",
                        "23",
                        "-an",
                        str(seg_path),
                    ]
                )
                try:
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                    self._record_job(project_id, scene.scene_id, "COMPLETED", seg_path, input_hash, " ".join(cmd), "")
                except subprocess.CalledProcessError as exc:
                    self._record_job(
                        project_id, scene.scene_id, "FAILED", None, input_hash, " ".join(cmd), exc.stderr[-500:]
                    )
                    raise
            rendered_segments.append(seg_path)
            timeline_entries.append(
                {
                    "scene_id": scene.scene_id,
                    "section_title": scene.section_title,
                    "segment_path": str(seg_path),
                    "duration_sec": scene.estimated_duration_sec,
                    "transition_in": scene.transition_in,
                    "transition_out": scene.transition_out,
                }
            )

        # Write FFmpeg chapter metadata
        ffmeta_path = self._write_chapter_metadata(scenes)

        final_mp4 = self.final_dir / "final_video.mp4"
        video_only_mp4 = self.final_dir / "video_assembled.mp4"

        if enable_transitions and len(rendered_segments) >= 2:
            self._assemble_with_xfade(ffmpeg_exe, rendered_segments, scenes, video_only_mp4, preset, fps)
        else:
            concat_file = self.final_dir / "concat_list.txt"
            concat_file.write_text(
                "\n".join(f"file '{seg.resolve().as_posix()}'" for seg in rendered_segments), encoding="utf-8"
            )
            subprocess.run(
                [ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c:v", "copy", str(video_only_mp4)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )

        mux_cmd = [
            ffmpeg_exe,
            "-y",
            "-i",
            str(video_only_mp4),
            "-i",
            str(narration_wav),
            "-i",
            str(ffmeta_path),
            "-map_metadata",
            "2",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(final_mp4),
        ]
        subprocess.run(mux_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

        otio_path = export_otio_timeline(
            project_name=project_id,
            scenes=scenes,
            narration_wav=narration_wav,
            output_path=self.final_dir / "timeline.otio",
            fps=fps,
        )

        manifest = {
            "project_id": project_id,
            "final_video": str(final_mp4),
            "subtitles_srt": str(subtitles_srt) if subtitles_srt else None,
            "otio_timeline": str(otio_path),
            "chapters_ffmeta": str(ffmeta_path),
            "resolution": resolution,
            "fps": fps,
            "preset": preset,
            "transitions_enabled": enable_transitions,
            "scenes_rendered": len(rendered_segments),
            "file_size_bytes": final_mp4.stat().st_size if final_mp4.exists() else 0,
            "timeline": timeline_entries,
            "mux_command": " ".join(mux_cmd),
            "rendered_at": utc_now_iso(),
        }
        (self.final_dir / "timeline.json").write_text(json.dumps(timeline_entries, indent=2), encoding="utf-8")
        (self.final_dir / "render_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (self.final_dir / "render_report.md").write_text(
            f"# Render Report\n\n- Output: `{final_mp4}`\n- OTIO: `{otio_path}`\n- Size: {manifest['file_size_bytes']} bytes\n- Scenes: {len(rendered_segments)}\n",
            encoding="utf-8",
        )
        return manifest

    @staticmethod
    def render_dubbed_variant(
        project_dir: Path,
        language_code: str,
        base_video: Path,
        narration_wav: Path,
        subtitles_srt: Path,
    ) -> dict:
        """Mux a separately generated language narration onto the approved picture edit."""
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            raise RuntimeError("FFmpeg executable not found.")
        if not base_video.is_file():
            raise FileNotFoundError(f"Base documentary video not found: {base_video}")
        if not narration_wav.is_file() or not subtitles_srt.is_file():
            raise FileNotFoundError("Translated narration and subtitles are required.")
        if not re.fullmatch(r"[a-z]{2}", language_code.lower()):
            raise ValueError("Language code must be a two-letter ISO 639-1 code.")
        output_dir = Path(project_dir) / "render" / "languages" / language_code.lower()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_video = output_dir / f"documentary_{language_code.lower()}.mp4"
        command = [
            ffmpeg, "-y", "-i", str(base_video), "-i", str(narration_wav),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-shortest",
            "-movflags", "+faststart", str(output_video),
        ]
        subprocess.run(
            command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
        )
        if not output_video.is_file() or output_video.stat().st_size == 0:
            raise RuntimeError("FFmpeg did not create the language-specific documentary.")
        return {
            "status": "DUBBED_VIDEO_RENDERED",
            "language_code": language_code.lower(),
            "video_path": str(output_video),
            "subtitle_path": str(subtitles_srt),
            "base_video": str(base_video),
            "file_size_bytes": output_video.stat().st_size,
            "video_stream_source": "BASE_DOCUMENTARY",
            "audio_stream_source": "TRANSLATED_PIPER_NARRATION",
            "subtitles_embedded": False,
            "subtitles_sidecar": True,
        }

    def _assemble_with_xfade(
        self,
        ffmpeg_exe: str,
        segments: list[Path],
        scenes: list[SceneSpec],
        out_mp4: Path,
        preset: str,
        fps: int,
    ) -> None:
        """Assemble scene MP4s with restrained cross-dissolve / wipe xfade transitions."""
        trans_dur = 0.4
        cmd = [ffmpeg_exe, "-y"]
        for seg in segments:
            cmd.extend(["-i", str(seg)])

        filters: list[str] = []
        offset = max(0.5, scenes[0].estimated_duration_sec - trans_dur)
        prev_label = "[0:v]"
        for idx in range(1, len(segments)):
            out_label = f"[v{idx}]" if idx < len(segments) - 1 else "[vout]"
            xfade_name = "wipeleft" if scenes[idx - 1].transition_out == "slide_left" else "fade"
            filters.append(f"{prev_label}[{idx}:v]xfade=transition={xfade_name}:duration={trans_dur}:offset={offset:.2f}{out_label}")
            prev_label = out_label
            offset += max(0.5, scenes[idx].estimated_duration_sec - trans_dur)

        cmd.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[vout]",
                "-r",
                str(fps),
                "-c:v",
                "libx264",
                "-preset",
                preset,
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                str(out_mp4),
            ]
        )
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

    def _write_chapter_metadata(self, scenes: list[SceneSpec]) -> Path:
        lines = [";FFMETADATA1"]
        cursor_ms = 0
        for s in scenes:
            dur_ms = int(round(s.estimated_duration_sec * 1000))
            lines.extend(
                [
                    "[CHAPTER]",
                    "TIMEBASE=1/1000",
                    f"START={cursor_ms}",
                    f"END={cursor_ms + dur_ms}",
                    f"title={s.scene_id}: {s.section_title}",
                ]
            )
            cursor_ms += dur_ms
        path = self.final_dir / "chapters.ffmeta"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def _is_cached(self, project_id: str, scene_id: str, input_hash: str, seg_path: Path) -> bool:
        if not seg_path.exists() or seg_path.stat().st_size == 0:
            return False
        row = self.conn.execute(
            "SELECT status, input_hash FROM render_jobs WHERE project_id = ? AND scene_id = ? ORDER BY updated_at DESC LIMIT 1",
            (project_id, scene_id),
        ).fetchone()
        return bool(row and row["status"] == "COMPLETED" and row["input_hash"] == input_hash)

    def _record_job(
        self,
        project_id: str,
        scene_id: str,
        status: str,
        output_path: Path | None,
        input_hash: str,
        command: str,
        error_message: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO render_jobs (
                id, project_id, scene_id, status, output_path, input_hash, command, error_message, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"job_{uuid.uuid4().hex[:8]}",
                project_id,
                scene_id,
                status,
                str(output_path) if output_path else None,
                input_hash,
                command,
                error_message,
                utc_now_iso(),
            ),
        )
        self.conn.commit()
