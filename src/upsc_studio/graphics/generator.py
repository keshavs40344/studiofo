"""Original educational graphics, flowcharts, and slide generator using Pillow."""

from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from upsc_studio.db.schemas import RightsStatus, SceneSpec
from upsc_studio.graphics.rights import AssetRightsLedger


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load Windows system font supporting English + Devanagari where available."""
    candidates = (
        [
            "C:/Windows/Fonts/NirmalaB.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
        if bold
        else [
            "C:/Windows/Fonts/Nirmala.ttc",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
    )
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


class GraphicsGenerator:
    """Generates clean, high-contrast 1920x1080 educational slides, flowcharts, and cards."""

    BG_COLOR = (15, 23, 42)         # Deep slate #0F172A
    CARD_COLOR = (30, 41, 59)       # Slate-800 #1E293B
    ACCENT_GOLD = (245, 158, 11)    # Amber-500 #F59E0B
    ACCENT_BLUE = (56, 189, 248)    # Sky-400 #38BDF8
    TEXT_PRIMARY = (248, 250, 252)  # Slate-50
    TEXT_MUTED = (148, 163, 184)    # Slate-400

    def __init__(self, project_dir: Path, rights_ledger: AssetRightsLedger) -> None:
        self.project_dir = project_dir
        self.out_dir = project_dir / "assets" / "generated"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.rights_ledger = rights_ledger

    def generate_scene_graphic(
        self,
        project_id: str,
        chapter_title: str,
        scene: SceneSpec,
        width: int = 1920,
        height: int = 1080,
    ) -> Path:
        """Render a crisp educational graphic for a scene and register its ORIGINAL_GENERATED rights."""
        img = Image.new("RGB", (width, height), color=self.BG_COLOR)
        draw = ImageDraw.Draw(img)

        font_tag = _load_font(26, bold=True)
        font_title = _load_font(54, bold=True)
        font_body = _load_font(34, bold=False)
        font_footer = _load_font(22, bold=False)

        # Safe margins: 96px horizontal, 72px vertical
        margin_x = 96
        draw.rectangle([0, 0, width, 10], fill=self.ACCENT_GOLD)
        draw.text(
            (margin_x, 56),
            f"UPSC STUDIO  |  {chapter_title.upper()}  |  {scene.visual_category.upper()}",
            fill=self.ACCENT_GOLD,
            font=font_tag,
        )

        # Scene title
        wrapped_title = textwrap.wrap(scene.on_screen_title, width=48) or [scene.on_screen_title]
        y = 112
        if len(wrapped_title) > 3:
            raise ValueError(
                f"{scene.scene_id}: title needs {len(wrapped_title)} lines; "
                "shorten the authored title instead of silently clipping it."
            )
        for line in wrapped_title:
            draw.text((margin_x, y), line, fill=self.TEXT_PRIMARY, font=font_title)
            y += 66

        # Content area: Flowchart boxes vs structured bullet cards
        y_content = y + 36
        if "Flowchart" in scene.visual_category:
            self._draw_flowchart(draw, margin_x, y_content, width - 2 * margin_x, scene.on_screen_bullets, font_body)
        else:
            self._draw_bullet_cards(
                draw, margin_x, y_content, width - 2 * margin_x, scene.on_screen_bullets,
                font_body, max_y=height - 124,
            )

        # Citation footer: wrap source text and fail rather than silently truncate.
        citation_text = "Sources: " + ("; ".join(scene.source_citations) if scene.source_citations else "Attribution pending review")
        footer_lines = textwrap.wrap(citation_text, width=116) or [citation_text]
        if len(footer_lines) > 2:
            raise ValueError(
                f"{scene.scene_id}: source attribution does not fit the footer; "
                "use concise source titles and retain full provenance in the project report."
            )
        draw.line([(margin_x, height - 92), (width - margin_x, height - 92)], fill=self.CARD_COLOR, width=2)
        for line_index, line in enumerate(footer_lines):
            draw.text((margin_x, height - 72 + line_index * 24), line, fill=self.TEXT_MUTED, font=font_footer)
        draw.text((width - 260, height - 72), f"Scene {scene.scene_id}", fill=self.ACCENT_BLUE, font=font_footer)

        out_path = self.out_dir / f"{scene.scene_id}.png"
        img.save(out_path, format="PNG")

        self.rights_ledger.register_asset(
            project_id=project_id,
            asset_type="generated_slide",
            file_path=out_path,
            creator="UPSC Studio GraphicsGenerator",
            licence="ORIGINAL_GENERATED",
            rights_status=RightsStatus.ORIGINAL_GENERATED,
            attribution="Original educational graphic generated by UPSC Studio",
        )
        return out_path

    def _draw_bullet_cards(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        box_w: int,
        bullets: list[str],
        font: ImageFont.ImageFont,
        max_y: int,
    ) -> None:
        curr_y = y
        for idx, bullet in enumerate(bullets[:4], start=1):
            lines = textwrap.wrap(bullet, width=74) or [bullet]
            card_h = 44 + len(lines) * 44
            if curr_y + card_h > max_y:
                raise ValueError(
                    f"Bullet card {idx} exceeds the safe content area; split the scene "
                    "or shorten the authored on-screen copy."
                )
            draw.rounded_rectangle(
                [x, curr_y, x + box_w, curr_y + card_h],
                radius=14,
                fill=self.CARD_COLOR,
                outline=self.ACCENT_BLUE if idx == 1 else (51, 65, 85),
                width=2,
            )
            draw.text((x + 28, curr_y + 20), f"0{idx}.", fill=self.ACCENT_GOLD, font=font)
            line_y = curr_y + 20
            for line in lines:
                draw.text((x + 100, line_y), line, fill=self.TEXT_PRIMARY, font=font)
                line_y += 44
            curr_y += card_h + 24

    def _draw_flowchart(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        total_w: int,
        steps: list[str],
        font: ImageFont.ImageFont,
    ) -> None:
        if not steps:
            raise ValueError("Flowchart graphic requires supplied, topic-specific steps.")
        if len(steps) > 3:
            raise ValueError("Flowchart graphic supports at most three nodes; split the scene rather than dropping steps.")
        items = steps
        step_w = (total_w - 80) // max(1, len(items))
        box_h = 340
        for idx, step in enumerate(items):
            bx = x + idx * (step_w + 40)
            draw.rounded_rectangle(
                [bx, y + 60, bx + step_w, y + 60 + box_h],
                radius=18,
                fill=self.CARD_COLOR,
                outline=self.ACCENT_GOLD,
                width=3,
            )
            draw.text((bx + 24, y + 84), f"STAGE {idx + 1}", fill=self.ACCENT_GOLD, font=font)
            ly = y + 146
            wrapped_step = textwrap.wrap(step, width=24) or [step]
            if len(wrapped_step) > 4:
                raise ValueError(
                    f"Flowchart node {idx + 1} exceeds its text area; split the node into another scene."
                )
            for line in wrapped_step:
                draw.text((bx + 24, ly), line, fill=self.TEXT_PRIMARY, font=font)
                ly += 44
            if idx < len(items) - 1:
                ax1 = bx + step_w + 6
                ax2 = bx + step_w + 34
                ay = y + 60 + box_h // 2
                draw.line([(ax1, ay), (ax2, ay)], fill=self.ACCENT_BLUE, width=5)
