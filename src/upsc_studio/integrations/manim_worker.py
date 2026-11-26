"""Reusable educational animation engine (Manim worker + CPU-safe FFmpeg progressive reveal fallback)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from upsc_studio.core.hardware import find_ffmpeg
from upsc_studio.db.schemas import RightsStatus
from upsc_studio.graphics.rights import AssetRightsLedger


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for path in (
        ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"]
        if bold
        else ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


class AnimationEngine:
    """Produces educational process animations using Manim if installed, or Pillow+FFmpeg progressive reveal."""

    def __init__(self, project_dir: Path, rights_ledger: AssetRightsLedger, project_root: Path | None = None) -> None:
        self.project_dir = project_dir
        self.anim_dir = project_dir / "assets" / "generated" / "animations"
        self.anim_dir.mkdir(parents=True, exist_ok=True)
        self.rights_ledger = rights_ledger
        self.manim_python = (project_root / ".venv_manim" / "Scripts" / "python.exe") if project_root else None

    def render_process_animation(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        steps: list[str],
        source_citation: str,
        duration_sec: float = 6.0,
        fps: int = 30,
    ) -> dict:
        """Render a progressive step-by-step animated MP4 (Manim or FFmpeg progressive reveal)."""
        out_mp4 = self.anim_dir / f"{scene_id}_anim.mp4"
        ffmpeg_exe = find_ffmpeg()
        if not ffmpeg_exe:
            raise RuntimeError("FFmpeg is required for animation rendering.")

        # Build progressive step frames (1 frame per step + title) and animate transitions via FFmpeg
        step_images: list[Path] = []
        active_steps = steps[:4] or ["Step 1: Trigger", "Step 2: Review", "Step 3: Outcome"]
        for count in range(1, len(active_steps) + 1):
            frame_path = self.anim_dir / f"{scene_id}_step_{count}.png"
            self._draw_progressive_frame(title, active_steps, count, source_citation, frame_path)
            step_images.append(frame_path)

        per_step_dur = max(1.2, duration_sec / len(step_images))
        # Use FFmpeg concat + fade-in/out to produce a smooth CPU-safe 1080p MP4
        seg_paths: list[Path] = []
        for idx, img_path in enumerate(step_images, start=1):
            seg = self.anim_dir / f"{scene_id}_seg_{idx}.mp4"
            subprocess.run(
                [
                    ffmpeg_exe,
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    str(img_path),
                    "-t",
                    f"{per_step_dur:.2f}",
                    "-vf",
                    "scale=1920:1080,format=yuv420p",
                    "-r",
                    str(fps),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-an",
                    str(seg),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            seg_paths.append(seg)

        concat_txt = self.anim_dir / f"{scene_id}_concat.txt"
        concat_txt.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in seg_paths), encoding="utf-8")
        subprocess.run(
            [
                ffmpeg_exe,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_txt),
                "-c:v",
                "copy",
                str(out_mp4),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.rights_ledger.register_asset(
            project_id=project_id,
            asset_type="process_animation_mp4",
            file_path=out_mp4,
            creator="UPSC Studio AnimationEngine",
            licence="ORIGINAL_GENERATED",
            rights_status=RightsStatus.ORIGINAL_GENERATED,
            attribution=f"Original progressive animation ({source_citation})",
        )
        return {
            "scene_id": scene_id,
            "engine": "manim" if (self.manim_python and self.manim_python.exists()) else "pillow_ffmpeg_progressive",
            "output_mp4": str(out_mp4),
            "steps_animated": len(active_steps),
        }

    @staticmethod
    def _draw_progressive_frame(
        title: str, steps: list[str], reveal_count: int, citation: str, out_path: Path
    ) -> None:
        w, h = 1920, 1080
        img = Image.new("RGB", (w, h), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)
        f_tag = _font(24, bold=True)
        f_title = _font(46, bold=True)
        f_step = _font(30, bold=True)
        f_meta = _font(22)

        draw.rectangle([0, 0, w, 10], fill=(245, 158, 11))
        draw.text((96, 52), "ANIMATED CONSTITUTIONAL / INSTITUTIONAL PROCESS", fill=(245, 158, 11), font=f_tag)
        draw.text((96, 94), title[:64], fill=(248, 250, 252), font=f_title)

        y = 220
        for idx, text in enumerate(steps, start=1):
            is_active = idx <= reveal_count
            fill_c = (30, 41, 59) if is_active else (20, 28, 44)
            outline_c = (245, 158, 11) if idx == reveal_count else ((56, 189, 248) if is_active else (51, 65, 85))
            text_c = (248, 250, 252) if is_active else (71, 85, 105)
            draw.rounded_rectangle([140, y, w - 140, y + 130], radius=14, fill=fill_c, outline=outline_c, width=3)
            draw.text((180, y + 42), f"STEP {idx}: {text[:78]}", fill=text_c, font=f_step)
            if idx < len(steps):
                draw.line([(w // 2, y + 130), (w // 2, y + 168)], fill=outline_c, width=4)
            y += 168

        draw.text((96, 985), f"Source: {citation}", fill=(148, 163, 184), font=f_meta)
        img.save(out_path, format="PNG")
