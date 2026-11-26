"""Extended educational visual systems: data charts, split-screen comparisons, quiz reveals, and primary source cards."""

from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

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


class ExtendedVisualSystems:
    """Generates verified data charts, split-screen comparisons, quiz cards, and document walkthroughs."""

    def __init__(self, project_dir: Path, rights_ledger: AssetRightsLedger) -> None:
        self.out_dir = project_dir / "assets" / "generated"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.rights_ledger = rights_ledger

    def render_bar_chart(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        bars: list[tuple[str, float]],
        unit: str,
        source_label: str,
        ref_period: str,
    ) -> Path:
        """Render a source-cited data comparison bar chart (1920x1080)."""
        w, h = 1920, 1080
        img = Image.new("RGB", (w, h), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)
        f_tag = _font(24, bold=True)
        f_title = _font(44, bold=True)
        f_lbl = _font(28)
        f_meta = _font(22)

        draw.rectangle([0, 0, w, 10], fill=(56, 189, 248))
        draw.text((96, 50), f"DATA VISUALISATION ({unit})", fill=(56, 189, 248), font=f_tag)
        draw.text((96, 92), title[:68], fill=(248, 250, 252), font=f_title)

        max_val = max((v for _, v in bars), default=1.0) or 1.0
        chart_left, chart_right = 420, 1740
        max_bar_w = chart_right - chart_left
        y = 250
        for idx, (label, val) in enumerate(bars[:6]):
            bar_w = int((val / max_val) * max_bar_w)
            color = (245, 158, 11) if idx == 0 else (56, 189, 248)
            draw.text((96, y + 18), label[:22], fill=(226, 232, 240), font=f_lbl)
            draw.rounded_rectangle([chart_left, y, chart_left + max(10, bar_w), y + 72], radius=8, fill=color)
            draw.text((chart_left + bar_w + 20, y + 18), f"{val} {unit}", fill=(248, 250, 252), font=f_lbl)
            y += 112

        draw.text((96, 985), f"Source: {source_label} | Reference Period: {ref_period}", fill=(148, 163, 184), font=f_meta)
        out_path = self.out_dir / f"{scene_id}_chart.png"
        img.save(out_path, format="PNG")
        self.rights_ledger.register_asset(
            project_id=project_id,
            asset_type="data_chart",
            file_path=out_path,
            creator="UPSC Studio ExtendedVisualSystems",
            licence="ORIGINAL_GENERATED",
            rights_status=RightsStatus.ORIGINAL_GENERATED,
            attribution=f"Original chart from {source_label} ({ref_period})",
        )
        return out_path

    def render_split_comparison(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        left_header: str,
        left_points: list[str],
        right_header: str,
        right_points: list[str],
        source_label: str,
    ) -> Path:
        """Render a before/after or comparative split-screen visual (1920x1080)."""
        w, h = 1920, 1080
        img = Image.new("RGB", (w, h), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)
        f_title = _font(44, bold=True)
        f_hdr = _font(32, bold=True)
        f_body = _font(28)
        f_meta = _font(22)

        draw.text((96, 60), title[:68], fill=(248, 250, 252), font=f_title)
        # Left panel
        draw.rounded_rectangle([96, 160, 930, 920], radius=16, fill=(30, 41, 59), outline=(245, 158, 11), width=3)
        draw.text((130, 190), left_header[:36], fill=(245, 158, 11), font=f_hdr)
        ly = 270
        for pt in left_points[:5]:
            for line in textwrap.wrap(f"• {pt}", width=44)[:2]:
                draw.text((130, ly), line, fill=(248, 250, 252), font=f_body)
                ly += 42
            ly += 24

        # Right panel
        draw.rounded_rectangle([990, 160, 1824, 920], radius=16, fill=(30, 41, 59), outline=(56, 189, 248), width=3)
        draw.text((1024, 190), right_header[:36], fill=(56, 189, 248), font=f_hdr)
        ry = 270
        for pt in right_points[:5]:
            for line in textwrap.wrap(f"• {pt}", width=44)[:2]:
                draw.text((1024, ry), line, fill=(248, 250, 252), font=f_body)
                ry += 42
            ry += 24

        draw.text((96, 985), f"Source: {source_label}", fill=(148, 163, 184), font=f_meta)
        out_path = self.out_dir / f"{scene_id}_split.png"
        img.save(out_path, format="PNG")
        self.rights_ledger.register_asset(
            project_id=project_id,
            asset_type="split_comparison",
            file_path=out_path,
            creator="UPSC Studio ExtendedVisualSystems",
            licence="ORIGINAL_GENERATED",
            rights_status=RightsStatus.ORIGINAL_GENERATED,
            attribution=f"Original comparison ({source_label})",
        )
        return out_path
