"""CPU-friendly documentary animation suite with 10 educational animation components.

Renders progressive educational animations using Pillow frame synthesis + FFmpeg x264 concatenation.
Features SHA-256 caching, WCAG AA compliance, and both 16:9 and 9:16 layout support.
"""
from __future__ import annotations

import hashlib
import subprocess
import textwrap
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw

from upsc_studio.core.hardware import find_ffmpeg
from upsc_studio.db.schemas import RightsStatus
from upsc_studio.graphics.design_system import (
    ColorPalette,
    FontManager,
    LAYOUT_SPECS,
    LayoutOrientation,
)
from upsc_studio.graphics.rights import AssetRightsLedger


class DocumentaryAnimationSuite:
    """Produces 10 distinct documentary animation types optimized for CPU-safe rendering."""

    def __init__(self, project_dir: Path, rights_ledger: AssetRightsLedger) -> None:
        self.project_dir = project_dir
        self.anim_dir = project_dir / "assets" / "generated" / "animations"
        self.anim_dir.mkdir(parents=True, exist_ok=True)
        self.rights_ledger = rights_ledger
        self.ffmpeg_exe = find_ffmpeg()

    def _cache_key(self, name: str, **kwargs) -> str:
        data = f"{name}|" + "|".join(f"{k}:{v}" for k, v in sorted(kwargs.items()))
        return hashlib.sha256(data.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _draw_wrapped_text(
        draw: ImageDraw.ImageDraw,
        text: str,
        position: tuple[int, int],
        font: Any,
        fill: tuple[int, int, int],
        max_width: int,
        max_lines: int = 2,
        line_gap: int = 6,
    ) -> int:
        """Word-wrap with measured pixel widths; raise instead of cropping text."""
        value = str(text or "").strip()
        if not value:
            return 0
        lines: list[str] = []
        current = ""

        def fits(candidate: str) -> bool:
            return draw.textlength(candidate, font=font) <= max_width

        for word in value.split():
            candidate = f"{current} {word}".strip()
            if fits(candidate):
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            if fits(word):
                current = word
                continue
            # Preserve long technical tokens by breaking them at character boundaries.
            chunk = ""
            for char in word:
                if chunk and not fits(chunk + char):
                    lines.append(chunk)
                    chunk = ""
                chunk += char
            current = chunk
        if current:
            lines.append(current)

        if len(lines) > max_lines:
            raise ValueError(
                f"Text needs {len(lines)} lines but layout permits {max_lines}; "
                "split the scene or reduce authored on-screen copy."
            )
        bbox = font.getbbox("Ag")
        line_height = max(1, bbox[3] - bbox[1]) + line_gap
        x, y = position
        for index, line in enumerate(lines):
            draw.text((x, y + index * line_height), line, fill=fill, font=font)
        return len(lines) * line_height

    @classmethod
    def _draw_source_footer(
        cls,
        draw: ImageDraw.ImageDraw,
        source_citation: str,
        x: int,
        y: int,
        max_width: int,
        font: Any,
    ) -> None:
        label = f"Source: {source_citation}" if source_citation else "Source attribution pending review"
        cls._draw_wrapped_text(
            draw, label, (x, y), font, ColorPalette.TEXT_MUTED,
            max_width=max_width, max_lines=2, line_gap=2,
        )

    def _render_frames_to_mp4(
        self,
        frames: list[Image.Image],
        output_mp4: Path,
        duration_sec: float = 4.0,
        fps: int = 30,
        orientation: LayoutOrientation = LayoutOrientation.LANDSCAPE_16_9,
    ) -> Path:
        """Encode synthesized PIL frames into a clean, CPU-safe MP4 clip using FFmpeg."""
        if not self.ffmpeg_exe:
            # Fallback: save last frame as image if ffmpeg is missing
            fallback_png = output_mp4.with_suffix(".png")
            frames[-1].save(fallback_png, format="PNG")
            return fallback_png

        spec = LAYOUT_SPECS[orientation]
        w, h = spec["width"], spec["height"]

        temp_dir = output_mp4.parent / f"tmp_{output_mp4.stem}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        frame_paths: list[Path] = []
        for idx, frame in enumerate(frames):
            p = temp_dir / f"frame_{idx:03d}.png"
            frame.save(p, format="PNG")
            frame_paths.append(p)

        per_frame_dur = max(0.8, duration_sec / len(frames))
        seg_paths: list[Path] = []

        try:
            for idx, fpath in enumerate(frame_paths):
                seg = temp_dir / f"seg_{idx:03d}.mp4"
                subprocess.run(
                    [
                        self.ffmpeg_exe,
                        "-y",
                        "-loop",
                        "1",
                        "-i",
                        str(fpath),
                        "-t",
                        f"{per_frame_dur:.2f}",
                        "-vf",
                        f"scale={w}:{h},format=yuv420p",
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

            concat_txt = temp_dir / "concat.txt"
            concat_txt.write_text("\n".join(f"file '{s.resolve().as_posix()}'" for s in seg_paths), encoding="utf-8")

            subprocess.run(
                [
                    self.ffmpeg_exe,
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_txt),
                    "-c:v",
                    "copy",
                    str(output_mp4),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        finally:
            # Clean up temp frames
            for p in frame_paths + seg_paths:
                p.unlink(missing_ok=True)
            (temp_dir / "concat.txt").unlink(missing_ok=True)
            temp_dir.rmdir()

        return output_mp4

    # 1. Timeline Progression
    def render_timeline_progression(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        milestones: list[tuple[str, str]],
        source_citation: str,
        duration_sec: float = 4.0,
        orientation: LayoutOrientation = LayoutOrientation.LANDSCAPE_16_9,
    ) -> Path:
        cache_id = self._cache_key("timeline", t=title, m=str(milestones), s=source_citation, o=orientation.value)
        out_mp4 = self.anim_dir / f"{scene_id}_timeline_{cache_id}.mp4"
        if out_mp4.exists() and out_mp4.stat().st_size > 10000:
            return out_mp4

        spec = LAYOUT_SPECS[orientation]
        w, h = spec["width"], spec["height"]
        margins = spec["margins"]

        if len(milestones) < 2:
            raise ValueError("A historical timeline requires at least two sourced milestones.")
        if len(milestones) > 8:
            raise ValueError("Timeline supports at most eight milestones; split the timeline into scenes.")
        items = milestones
        frames: list[Image.Image] = []

        for reveal_count in range(1, len(items) + 1):
            img = Image.new("RGB", (w, h), color=ColorPalette.BG_DARK)
            draw = ImageDraw.Draw(img)
            f_tag = FontManager.get_font(22, bold=True)
            f_title = FontManager.get_font(spec["title_size"], bold=True)
            f_date = FontManager.get_font(spec["heading_size"], bold=True)
            f_body = FontManager.get_font(spec["body_size"], bold=False)
            f_meta = FontManager.get_font(spec["meta_size"], bold=False)

            draw.rectangle([0, 0, w, 8], fill=ColorPalette.ACCENT_GOLD)
            draw.text((margins.margin_x, margins.margin_top - 36), "TIMELINE PROGRESSION", fill=ColorPalette.ACCENT_GOLD, font=f_tag)
            self._draw_wrapped_text(draw, title, (margins.margin_x, margins.margin_top), f_title, ColorPalette.TEXT_PRIMARY, max_width=w - 2 * margins.margin_x, max_lines=2)

            gap_y = int((h - margins.margin_bottom - (margins.margin_top + 80)) / max(1, len(items)))
            for idx in range(reveal_count):
                m_date, m_desc = items[idx]
                curr_y = margins.margin_top + 80 + idx * gap_y
                is_active = (idx == reveal_count - 1)
                color = ColorPalette.ACCENT_GOLD if is_active else ColorPalette.ACCENT_SKY
                draw.ellipse([margins.margin_x, curr_y + 8, margins.margin_x + 28, curr_y + 36], fill=color)
                if idx < reveal_count - 1:
                    draw.line([(margins.margin_x + 14, curr_y + 36), (margins.margin_x + 14, curr_y + gap_y + 8)], fill=ColorPalette.BORDER_FOCUS, width=4)

                draw.text((margins.margin_x + 50, curr_y), m_date, fill=color, font=f_date)
                self._draw_wrapped_text(draw, m_desc, (margins.margin_x + 50, curr_y + 36), f_body, ColorPalette.TEXT_PRIMARY, max_width=w - margins.margin_x - (margins.margin_x + 50), max_lines=2)

            self._draw_source_footer(draw, source_citation, margins.margin_x, h - margins.margin_bottom + 10, w - 2 * margins.margin_x, f_meta)
            frames.append(img)

        self._render_frames_to_mp4(frames, out_mp4, duration_sec, orientation=orientation)
        self.rights_ledger.register_asset(
            project_id=project_id,
            asset_type="timeline_animation_mp4",
            file_path=out_mp4,
            creator="UPSC Studio DocumentaryAnimationSuite",
            licence="ORIGINAL_GENERATED",
            rights_status=RightsStatus.ORIGINAL_GENERATED,
            attribution=f"Timeline animation ({source_citation})",
        )
        return out_mp4

    # 2. Cause-and-Effect Sequences
    def render_cause_and_effect(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        cause: str,
        mechanism: str,
        effect: str,
        source_citation: str,
        duration_sec: float = 4.0,
        orientation: LayoutOrientation = LayoutOrientation.LANDSCAPE_16_9,
    ) -> Path:
        cache_id = self._cache_key("cause_effect", t=title, c=cause, m=mechanism, e=effect, s=source_citation, o=orientation.value)
        out_mp4 = self.anim_dir / f"{scene_id}_cause_effect_{cache_id}.mp4"
        if out_mp4.exists() and out_mp4.stat().st_size > 10000:
            return out_mp4

        spec = LAYOUT_SPECS[orientation]
        w, h = spec["width"], spec["height"]
        margins = spec["margins"]

        stages = [
            ("01. CAUSE / TRIGGER", cause, ColorPalette.ACCENT_ROSE),
            ("02. OPERATIONAL MECHANISM", mechanism, ColorPalette.ACCENT_SKY),
            ("03. CONSEQUENCE / OUTCOME", effect, ColorPalette.ACCENT_EMERALD),
        ]
        frames: list[Image.Image] = []

        for step in range(1, len(stages) + 1):
            img = Image.new("RGB", (w, h), color=ColorPalette.BG_DARK)
            draw = ImageDraw.Draw(img)
            f_tag = FontManager.get_font(22, bold=True)
            f_title = FontManager.get_font(spec["title_size"], bold=True)
            f_step = FontManager.get_font(spec["heading_size"], bold=True)
            f_body = FontManager.get_font(spec["body_size"], bold=False)
            f_meta = FontManager.get_font(spec["meta_size"], bold=False)

            draw.rectangle([0, 0, w, 8], fill=ColorPalette.ACCENT_SKY)
            draw.text((margins.margin_x, margins.margin_top - 36), "CAUSE & EFFECT ANALYSIS", fill=ColorPalette.ACCENT_SKY, font=f_tag)
            self._draw_wrapped_text(draw, title, (margins.margin_x, margins.margin_top), f_title, ColorPalette.TEXT_PRIMARY, max_width=w - 2 * margins.margin_x, max_lines=2)

            box_w = w - 2 * margins.margin_x
            box_h = 130
            y_start = margins.margin_top + 100
            for idx in range(step):
                s_lbl, s_text, s_color = stages[idx]
                curr_y = y_start + idx * (box_h + 36)
                draw.rounded_rectangle([margins.margin_x, curr_y, margins.margin_x + box_w, curr_y + box_h], radius=14, fill=ColorPalette.SURFACE_CARD, outline=s_color, width=3)
                draw.text((margins.margin_x + 28, curr_y + 18), s_lbl, fill=s_color, font=f_step)
                self._draw_wrapped_text(draw, s_text, (margins.margin_x + 28, curr_y + 68), f_body, ColorPalette.TEXT_PRIMARY, max_width=box_w - 56, max_lines=2)

            self._draw_source_footer(draw, source_citation, margins.margin_x, h - margins.margin_bottom + 10, w - 2 * margins.margin_x, f_meta)
            frames.append(img)

        self._render_frames_to_mp4(frames, out_mp4, duration_sec, orientation=orientation)
        return out_mp4

    # 3. Process Demonstrations
    def render_process_demonstration(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        steps: list[str],
        source_citation: str,
        duration_sec: float = 4.0,
        orientation: LayoutOrientation = LayoutOrientation.LANDSCAPE_16_9,
    ) -> Path:
        cache_id = self._cache_key("process", t=title, s=str(steps), c=source_citation, o=orientation.value)
        out_mp4 = self.anim_dir / f"{scene_id}_process_{cache_id}.mp4"
        if out_mp4.exists() and out_mp4.stat().st_size > 10000:
            return out_mp4

        spec = LAYOUT_SPECS[orientation]
        w, h = spec["width"], spec["height"]
        margins = spec["margins"]

        if not steps:
            raise ValueError("A process demonstration requires at least one supplied step.")
        if len(steps) > 4:
            raise ValueError("Process animation supports at most four steps; split the process into scenes.")
        active_steps = steps
        frames: list[Image.Image] = []

        for count in range(1, len(active_steps) + 1):
            img = Image.new("RGB", (w, h), color=ColorPalette.BG_DARK)
            draw = ImageDraw.Draw(img)
            f_tag = FontManager.get_font(22, bold=True)
            f_title = FontManager.get_font(spec["title_size"], bold=True)
            f_step = FontManager.get_font(spec["heading_size"], bold=True)
            f_body = FontManager.get_font(spec["body_size"], bold=False)
            f_meta = FontManager.get_font(spec["meta_size"], bold=False)

            draw.rectangle([0, 0, w, 8], fill=ColorPalette.ACCENT_GOLD)
            draw.text((margins.margin_x, margins.margin_top - 36), "STEP-BY-STEP PROCESS DEMONSTRATION", fill=ColorPalette.ACCENT_GOLD, font=f_tag)
            self._draw_wrapped_text(draw, title, (margins.margin_x, margins.margin_top), f_title, ColorPalette.TEXT_PRIMARY, max_width=w - 2 * margins.margin_x, max_lines=2)

            box_w = w - 2 * margins.margin_x
            box_h = 110
            y_start = margins.margin_top + 90
            for idx in range(count):
                curr_y = y_start + idx * (box_h + 24)
                is_active = (idx == count - 1)
                outline_color = ColorPalette.ACCENT_GOLD if is_active else ColorPalette.BORDER_SUBTLE
                fill_color = ColorPalette.SURFACE_ELEVATED if is_active else ColorPalette.SURFACE_CARD
                draw.rounded_rectangle([margins.margin_x, curr_y, margins.margin_x + box_w, curr_y + box_h], radius=12, fill=fill_color, outline=outline_color, width=3)
                draw.text((margins.margin_x + 24, curr_y + 16), f"Step {idx + 1}", fill=ColorPalette.ACCENT_GOLD if is_active else ColorPalette.TEXT_MUTED, font=f_step)
                self._draw_wrapped_text(draw, active_steps[idx], (margins.margin_x + 140, curr_y + 16), f_body, ColorPalette.TEXT_PRIMARY, max_width=box_w - 164, max_lines=2)

            self._draw_source_footer(draw, source_citation, margins.margin_x, h - margins.margin_bottom + 10, w - 2 * margins.margin_x, f_meta)
            frames.append(img)

        self._render_frames_to_mp4(frames, out_mp4, duration_sec, orientation=orientation)
        return out_mp4

    # 4. Flow Diagrams
    def render_flow_diagram(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        condition: str,
        yes_branch: str,
        no_branch: str,
        source_citation: str,
        duration_sec: float = 4.0,
        orientation: LayoutOrientation = LayoutOrientation.LANDSCAPE_16_9,
    ) -> Path:
        cache_id = self._cache_key("flow", t=title, c=condition, y=yes_branch, n=no_branch, s=source_citation, o=orientation.value)
        out_mp4 = self.anim_dir / f"{scene_id}_flow_{cache_id}.mp4"
        if out_mp4.exists() and out_mp4.stat().st_size > 10000:
            return out_mp4

        spec = LAYOUT_SPECS[orientation]
        w, h = spec["width"], spec["height"]
        margins = spec["margins"]

        frames: list[Image.Image] = []
        for step in (1, 2):
            img = Image.new("RGB", (w, h), color=ColorPalette.BG_DARK)
            draw = ImageDraw.Draw(img)
            f_title = FontManager.get_font(spec["title_size"], bold=True)
            f_box = FontManager.get_font(spec["heading_size"], bold=True)
            f_body = FontManager.get_font(spec["body_size"], bold=False)
            f_meta = FontManager.get_font(spec["meta_size"], bold=False)

            self._draw_wrapped_text(draw, title, (margins.margin_x, margins.margin_top), f_title, ColorPalette.TEXT_PRIMARY, max_width=w - 2 * margins.margin_x, max_lines=2)
            # Decision Diamond / Central Box
            top_box_y = margins.margin_top + 100
            draw.rounded_rectangle([margins.margin_x + 200, top_box_y, w - margins.margin_x - 200, top_box_y + 140], radius=16, fill=ColorPalette.SURFACE_CARD, outline=ColorPalette.ACCENT_GOLD, width=3)
            draw.text((margins.margin_x + 240, top_box_y + 24), "CRITERIA / CONDITION TEST", fill=ColorPalette.ACCENT_GOLD, font=f_box)
            self._draw_wrapped_text(draw, condition, (margins.margin_x + 240, top_box_y + 76), f_body, ColorPalette.TEXT_PRIMARY, max_width=w - margins.margin_x - 240 - margins.margin_x, max_lines=2)

            if step >= 2:
                # Branches
                b_y = top_box_y + 220
                half_w = (w - 2 * margins.margin_x - 60) // 2
                # YES
                draw.rounded_rectangle([margins.margin_x, b_y, margins.margin_x + half_w, b_y + 160], radius=14, fill=ColorPalette.SURFACE_CARD, outline=ColorPalette.ACCENT_EMERALD, width=3)
                draw.text((margins.margin_x + 24, b_y + 20), "YES -> CONSEQUENCE", fill=ColorPalette.ACCENT_EMERALD, font=f_box)
                self._draw_wrapped_text(draw, yes_branch, (margins.margin_x + 24, b_y + 72), f_body, ColorPalette.TEXT_PRIMARY, max_width=half_w - 48, max_lines=2)

                # NO
                draw.rounded_rectangle([margins.margin_x + half_w + 60, b_y, w - margins.margin_x, b_y + 160], radius=14, fill=ColorPalette.SURFACE_CARD, outline=ColorPalette.ACCENT_ROSE, width=3)
                draw.text((margins.margin_x + half_w + 84, b_y + 20), "NO -> EXCEPTION", fill=ColorPalette.ACCENT_ROSE, font=f_box)
                self._draw_wrapped_text(draw, no_branch, (margins.margin_x + half_w + 84, b_y + 72), f_body, ColorPalette.TEXT_PRIMARY, max_width=half_w - 48, max_lines=2)

            self._draw_source_footer(draw, source_citation, margins.margin_x, h - margins.margin_bottom + 10, w - 2 * margins.margin_x, f_meta)
            frames.append(img)

        self._render_frames_to_mp4(frames, out_mp4, duration_sec, orientation=orientation)
        return out_mp4

    # 5. Institutional Relationships
    def render_institutional_relationship(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        institutions: list[tuple[str, str]],
        source_citation: str,
        duration_sec: float = 4.0,
        orientation: LayoutOrientation = LayoutOrientation.LANDSCAPE_16_9,
    ) -> Path:
        cache_id = self._cache_key("inst_rel", t=title, i=str(institutions), s=source_citation, o=orientation.value)
        out_mp4 = self.anim_dir / f"{scene_id}_inst_rel_{cache_id}.mp4"
        if out_mp4.exists() and out_mp4.stat().st_size > 10000:
            return out_mp4

        spec = LAYOUT_SPECS[orientation]
        w, h = spec["width"], spec["height"]
        margins = spec["margins"]

        if not institutions:
            raise ValueError("Institutional relationship rendering requires named, supplied institutions.")
        if len(institutions) > 3:
            raise ValueError("Institutional animation supports at most three nodes; split the diagram.")
        items = institutions
        frames: list[Image.Image] = []

        for count in range(1, len(items) + 1):
            img = Image.new("RGB", (w, h), color=ColorPalette.BG_DARK)
            draw = ImageDraw.Draw(img)
            f_title = FontManager.get_font(spec["title_size"], bold=True)
            f_hdr = FontManager.get_font(spec["heading_size"], bold=True)
            f_body = FontManager.get_font(spec["body_size"], bold=False)
            f_meta = FontManager.get_font(spec["meta_size"], bold=False)

            self._draw_wrapped_text(draw, title, (margins.margin_x, margins.margin_top), f_title, ColorPalette.TEXT_PRIMARY, max_width=w - 2 * margins.margin_x, max_lines=2)
            gap = int((w - 2 * margins.margin_x) / 3)
            box_w = gap - 30
            y_b = margins.margin_top + 160
            for idx in range(count):
                b_x = margins.margin_x + idx * gap
                lbl, role = items[idx]
                color = ColorPalette.ACCENT_GOLD if idx == count - 1 else ColorPalette.ACCENT_SKY
                draw.rounded_rectangle([b_x, y_b, b_x + box_w, y_b + 220], radius=16, fill=ColorPalette.SURFACE_CARD, outline=color, width=3)
                self._draw_wrapped_text(draw, lbl, (b_x + 20, y_b + 24), f_hdr, color, max_width=box_w - 40, max_lines=2)
                self._draw_wrapped_text(draw, role, (b_x + 20, y_b + 84), f_body, ColorPalette.TEXT_PRIMARY, max_width=box_w - 40, max_lines=2)

            self._draw_source_footer(draw, source_citation, margins.margin_x, h - margins.margin_bottom + 10, w - 2 * margins.margin_x, f_meta)
            frames.append(img)

        self._render_frames_to_mp4(frames, out_mp4, duration_sec, orientation=orientation)
        return out_mp4

    # 6. Map-Based Explanations
    def render_map_explanation(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        territories: list[tuple[str, str]],
        source_citation: str,
        duration_sec: float = 4.0,
        orientation: LayoutOrientation = LayoutOrientation.LANDSCAPE_16_9,
    ) -> Path:
        cache_id = self._cache_key("map_exp", t=title, t_list=str(territories), s=source_citation, o=orientation.value)
        out_mp4 = self.anim_dir / f"{scene_id}_map_exp_{cache_id}.mp4"
        if out_mp4.exists() and out_mp4.stat().st_size > 10000:
            return out_mp4

        spec = LAYOUT_SPECS[orientation]
        w, h = spec["width"], spec["height"]
        margins = spec["margins"]

        if len(territories) < 2:
            raise ValueError("Region-card rendering requires at least two supplied, sourced regions.")
        if len(territories) > 8:
            raise ValueError("Region-card animation supports at most eight regions; split the sequence.")
        items = territories
        frames: list[Image.Image] = []

        for count in range(1, len(items) + 1):
            img = Image.new("RGB", (w, h), color=ColorPalette.BG_DARK)
            draw = ImageDraw.Draw(img)
            f_title = FontManager.get_font(spec["title_size"], bold=True)
            f_hdr = FontManager.get_font(spec["heading_size"], bold=True)
            f_body = FontManager.get_font(spec["body_size"], bold=False)
            f_meta = FontManager.get_font(spec["meta_size"], bold=False)

            self._draw_wrapped_text(draw, title, (margins.margin_x, margins.margin_top), f_title, ColorPalette.TEXT_PRIMARY, max_width=w - 2 * margins.margin_x, max_lines=2)

            # Map highlight boxes
            for idx in range(count):
                zone, desc = items[idx]
                curr_y = margins.margin_top + 100 + idx * 130
                draw.rounded_rectangle([margins.margin_x, curr_y, w - margins.margin_x, curr_y + 100], radius=12, fill=ColorPalette.SURFACE_CARD, outline=ColorPalette.ACCENT_SKY, width=2)
                draw.text((margins.margin_x + 30, curr_y + 16), f"• {zone}", fill=ColorPalette.ACCENT_SKY, font=f_hdr)
                self._draw_wrapped_text(draw, desc, (margins.margin_x + 340, curr_y + 20), f_body, ColorPalette.TEXT_PRIMARY, max_width=w - margins.margin_x - 340 - margins.margin_x, max_lines=2)

            self._draw_source_footer(draw, source_citation, margins.margin_x, h - margins.margin_bottom + 10, w - 2 * margins.margin_x, f_meta)
            frames.append(img)

        self._render_frames_to_mp4(frames, out_mp4, duration_sec, orientation=orientation)
        return out_mp4

    # 7. Statistical Comparisons
    def render_statistical_comparison(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        stat_a: tuple[str, float],
        stat_b: tuple[str, float],
        unit: str,
        source_citation: str,
        duration_sec: float = 4.0,
        orientation: LayoutOrientation = LayoutOrientation.LANDSCAPE_16_9,
    ) -> Path:
        cache_id = self._cache_key("stat_comp", t=title, a=str(stat_a), b=str(stat_b), u=unit, s=source_citation, o=orientation.value)
        out_mp4 = self.anim_dir / f"{scene_id}_stat_comp_{cache_id}.mp4"
        if out_mp4.exists() and out_mp4.stat().st_size > 10000:
            return out_mp4

        spec = LAYOUT_SPECS[orientation]
        w, h = spec["width"], spec["height"]
        margins = spec["margins"]

        frames: list[Image.Image] = []
        for step in (1, 2):
            img = Image.new("RGB", (w, h), color=ColorPalette.BG_DARK)
            draw = ImageDraw.Draw(img)
            f_title = FontManager.get_font(spec["title_size"], bold=True)
            f_hdr = FontManager.get_font(spec["heading_size"], bold=True)
            f_val = FontManager.get_font(56, bold=True)
            f_meta = FontManager.get_font(spec["meta_size"], bold=False)

            self._draw_wrapped_text(draw, title, (margins.margin_x, margins.margin_top), f_title, ColorPalette.TEXT_PRIMARY, max_width=w - 2 * margins.margin_x, max_lines=2)
            half_w = (w - 2 * margins.margin_x - 60) // 2

            # Left Stat
            draw.rounded_rectangle([margins.margin_x, margins.margin_top + 120, margins.margin_x + half_w, margins.margin_top + 460], radius=16, fill=ColorPalette.SURFACE_CARD, outline=ColorPalette.ACCENT_GOLD, width=3)
            self._draw_wrapped_text(draw, stat_a[0], (margins.margin_x + 40, margins.margin_top + 160), f_hdr, ColorPalette.ACCENT_GOLD, max_width=half_w - 80, max_lines=2)
            draw.text((margins.margin_x + 40, margins.margin_top + 260), f"{stat_a[1]} {unit}", fill=ColorPalette.TEXT_PRIMARY, font=f_val)

            # Right Stat
            if step >= 2:
                rx = margins.margin_x + half_w + 60
                draw.rounded_rectangle([rx, margins.margin_top + 120, rx + half_w, margins.margin_top + 460], radius=16, fill=ColorPalette.SURFACE_CARD, outline=ColorPalette.ACCENT_SKY, width=3)
                self._draw_wrapped_text(draw, stat_b[0], (rx + 40, margins.margin_top + 160), f_hdr, ColorPalette.ACCENT_SKY, max_width=half_w - 80, max_lines=2)
                draw.text((rx + 40, margins.margin_top + 260), f"{stat_b[1]} {unit}", fill=ColorPalette.TEXT_PRIMARY, font=f_val)

            self._draw_source_footer(draw, source_citation, margins.margin_x, h - margins.margin_bottom + 10, w - 2 * margins.margin_x, f_meta)
            frames.append(img)

        self._render_frames_to_mp4(frames, out_mp4, duration_sec, orientation=orientation)
        return out_mp4

    # 8. Before-and-After Comparisons
    def render_before_after_comparison(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        before_points: list[str],
        after_points: list[str],
        source_citation: str,
        duration_sec: float = 4.0,
        orientation: LayoutOrientation = LayoutOrientation.LANDSCAPE_16_9,
    ) -> Path:
        cache_id = self._cache_key("before_after", t=title, b=str(before_points), a=str(after_points), s=source_citation, o=orientation.value)
        out_mp4 = self.anim_dir / f"{scene_id}_before_after_{cache_id}.mp4"
        if out_mp4.exists() and out_mp4.stat().st_size > 10000:
            return out_mp4

        spec = LAYOUT_SPECS[orientation]
        w, h = spec["width"], spec["height"]
        margins = spec["margins"]

        frames: list[Image.Image] = []
        for step in (1, 2):
            img = Image.new("RGB", (w, h), color=ColorPalette.BG_DARK)
            draw = ImageDraw.Draw(img)
            f_title = FontManager.get_font(spec["title_size"], bold=True)
            f_hdr = FontManager.get_font(spec["heading_size"], bold=True)
            f_body = FontManager.get_font(spec["body_size"], bold=False)
            f_meta = FontManager.get_font(spec["meta_size"], bold=False)

            self._draw_wrapped_text(draw, title, (margins.margin_x, margins.margin_top), f_title, ColorPalette.TEXT_PRIMARY, max_width=w - 2 * margins.margin_x, max_lines=2)
            half_w = (w - 2 * margins.margin_x - 60) // 2

            # BEFORE
            draw.rounded_rectangle([margins.margin_x, margins.margin_top + 100, margins.margin_x + half_w, h - margins.margin_bottom - 40], radius=16, fill=ColorPalette.SURFACE_CARD, outline=ColorPalette.ACCENT_ROSE, width=3)
            draw.text((margins.margin_x + 30, margins.margin_top + 130), "PRE-REFORM STATUS", fill=ColorPalette.ACCENT_ROSE, font=f_hdr)
            y_pt = margins.margin_top + 200
            if len(before_points) > 3:
                raise ValueError("Before/after comparison supports at most three points per side; split the scene.")
            for pt in before_points:
                self._draw_wrapped_text(draw, f"• {pt}", (margins.margin_x + 30, y_pt), f_body, ColorPalette.TEXT_PRIMARY, max_width=half_w - 60, max_lines=2)
                y_pt += 60

            # AFTER
            if step >= 2:
                rx = margins.margin_x + half_w + 60
                draw.rounded_rectangle([rx, margins.margin_top + 100, rx + half_w, h - margins.margin_bottom - 40], radius=16, fill=ColorPalette.SURFACE_CARD, outline=ColorPalette.ACCENT_EMERALD, width=3)
                draw.text((rx + 30, margins.margin_top + 130), "POST-REFORM IMPACT", fill=ColorPalette.ACCENT_EMERALD, font=f_hdr)
                y_pt = margins.margin_top + 200
                if len(after_points) > 3:
                    raise ValueError("Before/after comparison supports at most three points per side; split the scene.")
                for pt in after_points:
                    self._draw_wrapped_text(draw, f"• {pt}", (rx + 30, y_pt), f_body, ColorPalette.TEXT_PRIMARY, max_width=half_w - 60, max_lines=2)
                    y_pt += 60

            self._draw_source_footer(draw, source_citation, margins.margin_x, h - margins.margin_bottom + 10, w - 2 * margins.margin_x, f_meta)
            frames.append(img)

        self._render_frames_to_mp4(frames, out_mp4, duration_sec, orientation=orientation)
        return out_mp4

    # 9. Scientific Processes
    def render_scientific_process(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        inputs: str,
        transformation: str,
        outputs: str,
        source_citation: str,
        duration_sec: float = 4.0,
        orientation: LayoutOrientation = LayoutOrientation.LANDSCAPE_16_9,
    ) -> Path:
        cache_id = self._cache_key("sci_proc", t=title, i=inputs, tr=transformation, o=outputs, s=source_citation, orient=orientation.value)
        out_mp4 = self.anim_dir / f"{scene_id}_sci_proc_{cache_id}.mp4"
        if out_mp4.exists() and out_mp4.stat().st_size > 10000:
            return out_mp4

        spec = LAYOUT_SPECS[orientation]
        w, h = spec["width"], spec["height"]
        margins = spec["margins"]

        stages = [("1. INPUTS / SUBSTRATES", inputs, ColorPalette.ACCENT_SKY), ("2. TRANSFORMATION CYCLE", transformation, ColorPalette.ACCENT_GOLD), ("3. OUTPUTS / BYPRODUCTS", outputs, ColorPalette.ACCENT_EMERALD)]
        frames: list[Image.Image] = []

        for count in range(1, len(stages) + 1):
            img = Image.new("RGB", (w, h), color=ColorPalette.BG_DARK)
            draw = ImageDraw.Draw(img)
            f_title = FontManager.get_font(spec["title_size"], bold=True)
            f_hdr = FontManager.get_font(spec["heading_size"], bold=True)
            f_body = FontManager.get_font(spec["body_size"], bold=False)
            f_meta = FontManager.get_font(spec["meta_size"], bold=False)

            self._draw_wrapped_text(draw, title, (margins.margin_x, margins.margin_top), f_title, ColorPalette.TEXT_PRIMARY, max_width=w - 2 * margins.margin_x, max_lines=2)
            gap = int((w - 2 * margins.margin_x) / 3)
            box_w = gap - 30
            y_b = margins.margin_top + 160
            for idx in range(count):
                b_x = margins.margin_x + idx * gap
                lbl, desc, col = stages[idx]
                draw.rounded_rectangle([b_x, y_b, b_x + box_w, y_b + 220], radius=16, fill=ColorPalette.SURFACE_CARD, outline=col, width=3)
                self._draw_wrapped_text(draw, lbl, (b_x + 20, y_b + 24), f_hdr, col, max_width=box_w - 40, max_lines=2)
                self._draw_wrapped_text(draw, desc, (b_x + 20, y_b + 84), f_body, ColorPalette.TEXT_PRIMARY, max_width=box_w - 40, max_lines=2)

            self._draw_source_footer(draw, source_citation, margins.margin_x, h - margins.margin_bottom + 10, w - 2 * margins.margin_x, f_meta)
            frames.append(img)

        self._render_frames_to_mp4(frames, out_mp4, duration_sec, orientation=orientation)
        return out_mp4

    # 10. Historical Changes
    def render_historical_changes(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        epoch_a: tuple[str, str],
        epoch_b: tuple[str, str],
        source_citation: str,
        duration_sec: float = 4.0,
        orientation: LayoutOrientation = LayoutOrientation.LANDSCAPE_16_9,
    ) -> Path:
        cache_id = self._cache_key("hist_change", t=title, a=str(epoch_a), b=str(epoch_b), s=source_citation, o=orientation.value)
        out_mp4 = self.anim_dir / f"{scene_id}_hist_change_{cache_id}.mp4"
        if out_mp4.exists() and out_mp4.stat().st_size > 10000:
            return out_mp4

        spec = LAYOUT_SPECS[orientation]
        w, h = spec["width"], spec["height"]
        margins = spec["margins"]

        frames: list[Image.Image] = []
        for step in (1, 2):
            img = Image.new("RGB", (w, h), color=ColorPalette.BG_DARK)
            draw = ImageDraw.Draw(img)
            f_title = FontManager.get_font(spec["title_size"], bold=True)
            f_hdr = FontManager.get_font(spec["heading_size"], bold=True)
            f_body = FontManager.get_font(spec["body_size"], bold=False)
            f_meta = FontManager.get_font(spec["meta_size"], bold=False)

            self._draw_wrapped_text(draw, title, (margins.margin_x, margins.margin_top), f_title, ColorPalette.TEXT_PRIMARY, max_width=w - 2 * margins.margin_x, max_lines=2)
            half_w = (w - 2 * margins.margin_x - 60) // 2

            # Epoch A
            draw.rounded_rectangle([margins.margin_x, margins.margin_top + 120, margins.margin_x + half_w, margins.margin_top + 460], radius=16, fill=ColorPalette.SURFACE_CARD, outline=ColorPalette.ACCENT_GOLD, width=3)
            self._draw_wrapped_text(draw, epoch_a[0], (margins.margin_x + 36, margins.margin_top + 160), f_hdr, ColorPalette.ACCENT_GOLD, max_width=half_w - 72, max_lines=2)
            self._draw_wrapped_text(draw, epoch_a[1], (margins.margin_x + 36, margins.margin_top + 240), f_body, ColorPalette.TEXT_PRIMARY, max_width=half_w - 72, max_lines=3)

            # Epoch B
            if step >= 2:
                rx = margins.margin_x + half_w + 60
                draw.rounded_rectangle([rx, margins.margin_top + 120, rx + half_w, margins.margin_top + 460], radius=16, fill=ColorPalette.SURFACE_CARD, outline=ColorPalette.ACCENT_SKY, width=3)
                self._draw_wrapped_text(draw, epoch_b[0], (rx + 36, margins.margin_top + 160), f_hdr, ColorPalette.ACCENT_SKY, max_width=half_w - 72, max_lines=2)
                self._draw_wrapped_text(draw, epoch_b[1], (rx + 36, margins.margin_top + 240), f_body, ColorPalette.TEXT_PRIMARY, max_width=half_w - 72, max_lines=3)

            self._draw_source_footer(draw, source_citation, margins.margin_x, h - margins.margin_bottom + 10, w - 2 * margins.margin_x, f_meta)
            frames.append(img)

        self._render_frames_to_mp4(frames, out_mp4, duration_sec, orientation=orientation)
        return out_mp4
