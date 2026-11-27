"""Evidence-backed educational graphics generator with strict data traceability and layout support."""

from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from upsc_studio.db.schemas import RightsStatus
from upsc_studio.graphics.design_system import (
    ColorPalette,
    FontManager,
    LAYOUT_SPECS,
    LayoutOrientation,
)
from upsc_studio.graphics.rights import AssetRightsLedger


class EvidenceGraphicsGenerator:
    """Generates verified 1080p landscape (16:9) and vertical shorts (9:16) educational graphics."""

    def __init__(self, project_dir: Path, rights_ledger: AssetRightsLedger) -> None:
        self.project_dir = project_dir
        self.out_dir = project_dir / "assets" / "generated"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.rights_ledger = rights_ledger

    def _cache_key(self, prefix: str, **kwargs) -> str:
        data = f"{prefix}|" + "|".join(f"{k}:{v}" for k, v in sorted(kwargs.items()))
        return hashlib.sha256(data.encode("utf-8")).hexdigest()[:12]

    def render_data_chart(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        bars: list[tuple[str, float]],
        unit: str,
        source_label: str,
        ref_period: str,
        orientation: LayoutOrientation = LayoutOrientation.LANDSCAPE_16_9,
    ) -> Path:
        """Render an evidence-backed quantitative bar chart.
        
        Requires verified source_label, ref_period, and unit.
        """
        if not source_label or not source_label.strip():
            raise ValueError("source_label is required for quantitative data charts.")
        if not ref_period or not ref_period.strip():
            raise ValueError("ref_period is required for quantitative data charts.")
        if not unit or not unit.strip():
            raise ValueError("unit of measurement is required for quantitative data charts.")
        if not bars:
            raise ValueError("At least one data point is required.")

        spec = LAYOUT_SPECS[orientation]
        w, h = spec["width"], spec["height"]
        margins = spec["margins"]

        cache_id = self._cache_key("chart", title=title, bars=str(bars), unit=unit, src=source_label, orient=orientation.value)
        out_path = self.out_dir / f"{scene_id}_chart_{cache_id}.png"
        if out_path.exists() and out_path.stat().st_size > 5000:
            return out_path

        img = Image.new("RGB", (w, h), color=ColorPalette.BG_DARK)
        draw = ImageDraw.Draw(img)

        f_tag = FontManager.get_font(22, bold=True)
        f_title = FontManager.get_font(spec["title_size"], bold=True)
        f_lbl = FontManager.get_font(spec["heading_size"], bold=False)
        f_val = FontManager.get_font(spec["heading_size"], bold=True)
        f_meta = FontManager.get_font(spec["meta_size"], bold=False)

        # Header accent bar
        draw.rectangle([0, 0, w, 8], fill=ColorPalette.ACCENT_SKY)
        draw.text((margins.margin_x, margins.margin_top - 36), f"DATA VISUALISATION  |  UNIT: {unit.upper()}", fill=ColorPalette.ACCENT_SKY, font=f_tag)

        # Title
        title_lines = textwrap.wrap(title, width=38 if orientation == LayoutOrientation.VERTICAL_9_16 else 60)
        curr_y = margins.margin_top
        for line in title_lines[:2]:
            draw.text((margins.margin_x, curr_y), line, fill=ColorPalette.TEXT_PRIMARY, font=f_title)
            curr_y += spec["title_size"] + 12

        # Draw bars
        max_val = max((v for _, v in bars), default=1.0) or 1.0
        chart_top = curr_y + 40
        available_height = h - margins.margin_bottom - chart_top
        num_bars = min(len(bars), 6 if orientation == LayoutOrientation.LANDSCAPE_16_9 else 5)
        bar_gap = 24
        bar_height = min(74, int((available_height - (num_bars - 1) * bar_gap) / num_bars))

        if orientation == LayoutOrientation.LANDSCAPE_16_9:
            label_w = 340
            max_bar_w = w - margins.margin_x - (margins.margin_x + label_w + 30) - 180
            for idx, (label, val) in enumerate(bars[:num_bars]):
                y_b = chart_top + idx * (bar_height + bar_gap)
                draw.text((margins.margin_x, y_b + 16), label[:24], fill=ColorPalette.TEXT_SECONDARY, font=f_lbl)
                bar_w = max(16, int((val / max_val) * max_bar_w))
                color = ColorPalette.ACCENT_GOLD if idx == 0 else ColorPalette.ACCENT_SKY
                bar_left = margins.margin_x + label_w + 20
                draw.rounded_rectangle([bar_left, y_b, bar_left + bar_w, y_b + bar_height], radius=8, fill=color)
                draw.text((bar_left + bar_w + 18, y_b + 16), f"{val} {unit}", fill=ColorPalette.TEXT_PRIMARY, font=f_val)
        else:
            # Vertical layout
            max_bar_w = w - 2 * margins.margin_x - 140
            for idx, (label, val) in enumerate(bars[:num_bars]):
                y_b = chart_top + idx * (bar_height + 48)
                draw.text((margins.margin_x, y_b), label[:30], fill=ColorPalette.TEXT_SECONDARY, font=f_lbl)
                bar_w = max(16, int((val / max_val) * max_bar_w))
                color = ColorPalette.ACCENT_GOLD if idx == 0 else ColorPalette.ACCENT_SKY
                draw.rounded_rectangle([margins.margin_x, y_b + 38, margins.margin_x + bar_w, y_b + 38 + 36], radius=8, fill=color)
                draw.text((margins.margin_x + bar_w + 16, y_b + 38), f"{val} {unit}", fill=ColorPalette.TEXT_PRIMARY, font=f_val)

        # Footer citation
        meta_str = f"Source: {source_label}  |  Ref Period: {ref_period}"
        draw.text((margins.margin_x, h - margins.margin_bottom + 10), meta_str[:100], fill=ColorPalette.TEXT_MUTED, font=f_meta)

        img.save(out_path, format="PNG")
        self.rights_ledger.register_asset(
            project_id=project_id,
            asset_type="evidence_data_chart",
            file_path=out_path,
            creator="UPSC Studio EvidenceGraphicsGenerator",
            licence="ORIGINAL_GENERATED",
            rights_status=RightsStatus.ORIGINAL_GENERATED,
            attribution=f"Evidence chart derived from {source_label} ({ref_period})",
        )
        return out_path

    def render_timeline(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        milestones: list[tuple[str, str]],
        source_label: str,
        orientation: LayoutOrientation = LayoutOrientation.LANDSCAPE_16_9,
    ) -> Path:
        """Render a chronological milestone timeline."""
        spec = LAYOUT_SPECS[orientation]
        w, h = spec["width"], spec["height"]
        margins = spec["margins"]

        cache_id = self._cache_key("timeline", title=title, milestones=str(milestones), src=source_label, orient=orientation.value)
        out_path = self.out_dir / f"{scene_id}_timeline_{cache_id}.png"
        if out_path.exists() and out_path.stat().st_size > 5000:
            return out_path

        img = Image.new("RGB", (w, h), color=ColorPalette.BG_DARK)
        draw = ImageDraw.Draw(img)

        f_tag = FontManager.get_font(22, bold=True)
        f_title = FontManager.get_font(spec["title_size"], bold=True)
        f_date = FontManager.get_font(spec["heading_size"], bold=True)
        f_body = FontManager.get_font(spec["body_size"], bold=False)
        f_meta = FontManager.get_font(spec["meta_size"], bold=False)

        draw.rectangle([0, 0, w, 8], fill=ColorPalette.ACCENT_GOLD)
        draw.text((margins.margin_x, margins.margin_top - 36), "HISTORICAL TIMELINE & EVOLUTION", fill=ColorPalette.ACCENT_GOLD, font=f_tag)

        draw.text((margins.margin_x, margins.margin_top), title[:54], fill=ColorPalette.TEXT_PRIMARY, font=f_title)

        y_top = margins.margin_top + 80
        items = milestones[:4]
        gap_y = int((h - margins.margin_bottom - y_top) / max(1, len(items)))

        for idx, (m_date, m_desc) in enumerate(items):
            curr_y = y_top + idx * gap_y
            # Bullet node
            draw.ellipse([margins.margin_x, curr_y + 8, margins.margin_x + 24, curr_y + 32], fill=ColorPalette.ACCENT_GOLD)
            if idx < len(items) - 1:
                draw.line([(margins.margin_x + 12, curr_y + 32), (margins.margin_x + 12, curr_y + gap_y + 8)], fill=ColorPalette.BORDER_SUBTLE, width=3)

            draw.text((margins.margin_x + 48, curr_y), m_date, fill=ColorPalette.ACCENT_GOLD, font=f_date)
            wrapped_desc = textwrap.wrap(m_desc, width=54 if orientation == LayoutOrientation.LANDSCAPE_16_9 else 34)
            d_y = curr_y + 36
            for line in wrapped_desc[:2]:
                draw.text((margins.margin_x + 48, d_y), line, fill=ColorPalette.TEXT_PRIMARY, font=f_body)
                d_y += spec["body_size"] + 6

        draw.text((margins.margin_x, h - margins.margin_bottom + 10), f"Source: {source_label}", fill=ColorPalette.TEXT_MUTED, font=f_meta)

        img.save(out_path, format="PNG")
        self.rights_ledger.register_asset(
            project_id=project_id,
            asset_type="historical_timeline",
            file_path=out_path,
            creator="UPSC Studio EvidenceGraphicsGenerator",
            licence="ORIGINAL_GENERATED",
            rights_status=RightsStatus.ORIGINAL_GENERATED,
            attribution=f"Timeline based on {source_label}",
        )
        return out_path
