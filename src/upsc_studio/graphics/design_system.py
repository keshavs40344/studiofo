"""Design system, color semantics, typography hierarchy, and WCAG AA contrast rules."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from PIL import ImageFont


class LayoutOrientation(str, Enum):
    LANDSCAPE_16_9 = "LANDSCAPE_16_9"  # 1920 x 1080
    VERTICAL_9_16 = "VERTICAL_9_16"    # 1080 x 1920 (YouTube Shorts / Mobile)


@dataclass(frozen=True)
class SafeMargins:
    margin_x: int
    margin_top: int
    margin_bottom: int


LAYOUT_SPECS = {
    LayoutOrientation.LANDSCAPE_16_9: {
        "width": 1920,
        "height": 1080,
        "margins": SafeMargins(margin_x=96, margin_top=72, margin_bottom=84),
        "title_size": 48,
        "heading_size": 34,
        "body_size": 26,
        "meta_size": 20,
    },
    LayoutOrientation.VERTICAL_9_16: {
        "width": 1080,
        "height": 1920,
        # Vertical Shorts requires clear safe zones for platform UI overlays
        "margins": SafeMargins(margin_x=72, margin_top=180, margin_bottom=320),
        "title_size": 52,
        "heading_size": 36,
        "body_size": 30,
        "meta_size": 22,
    },
}


class ColorPalette:
    """Design system color tokens with semantic meaning and accessible contrast."""

    # Surfaces
    BG_DARK = (15, 23, 42)          # Deep Slate (#0F172A)
    SURFACE_CARD = (30, 41, 59)      # Slate-800 (#1E293B)
    SURFACE_ELEVATED = (51, 65, 85)  # Slate-700 (#334155)

    # Borders & Dividers
    BORDER_SUBTLE = (51, 65, 85)     # Slate-700
    BORDER_FOCUS = (56, 189, 248)    # Sky-400

    # Typography
    TEXT_PRIMARY = (248, 250, 252)   # Slate-50 (White/High Contrast)
    TEXT_SECONDARY = (226, 232, 240) # Slate-200
    TEXT_MUTED = (148, 163, 184)     # Slate-400

    # Semantic Accents
    ACCENT_GOLD = (245, 158, 11)     # Amber-500 (Constitutional / Landmark / Authority)
    ACCENT_SKY = (56, 189, 248)      # Sky-400 (Institutional / Procedural / Logic)
    ACCENT_EMERALD = (16, 185, 129)  # Emerald-500 (Growth / Reforms / Success)
    ACCENT_ROSE = (244, 63, 94)      # Rose-500 (Alerts / Bottlenecks / Challenges)
    ACCENT_PURPLE = (168, 85, 247)   # Purple-500 (International / Theoretical)


def calculate_relative_luminance(rgb: tuple[int, int, int]) -> float:
    """Calculate relative luminance according to WCAG 2.1 specifications."""
    def _channel_lum(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else math.pow((s + 0.055) / 1.055, 2.4)

    r, g, b = rgb[:3]
    return 0.2126 * _channel_lum(r) + 0.7152 * _channel_lum(g) + 0.0722 * _channel_lum(b)


def calculate_contrast_ratio(rgb1: tuple[int, int, int], rgb2: tuple[int, int, int]) -> float:
    """Calculate WCAG contrast ratio between two RGB colors (returns 1.0 to 21.0)."""
    l1 = calculate_relative_luminance(rgb1)
    l2 = calculate_relative_luminance(rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def verify_wcag_aa(
    foreground: tuple[int, int, int],
    background: tuple[int, int, int],
    is_large_text: bool = False,
) -> bool:
    """Check if color combination passes WCAG AA contrast (>= 4.5 for normal, >= 3.0 for large)."""
    ratio = calculate_contrast_ratio(foreground, background)
    threshold = 3.0 if is_large_text else 4.5
    return ratio >= threshold


class FontManager:
    """Loads appropriate system fonts with Windows fallback for Devanagari and Latin scripts."""

    _font_cache: dict[tuple[int, bool], ImageFont.ImageFont] = {}

    @classmethod
    def get_font(cls, size: int, bold: bool = False) -> ImageFont.ImageFont:
        key = (size, bold)
        if key in cls._font_cache:
            return cls._font_cache[key]

        candidates = (
            [
                "C:/Windows/Fonts/NirmalaB.ttf",  # High-quality Devanagari + English Bold
                "C:/Windows/Fonts/segoeuib.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
            ]
            if bold
            else [
                "C:/Windows/Fonts/Nirmala.ttc",   # High-quality Devanagari + English Regular
                "C:/Windows/Fonts/segoeui.ttf",
                "C:/Windows/Fonts/arial.ttf",
            ]
        )
        for path in candidates:
            if Path(path).exists():
                try:
                    f = ImageFont.truetype(path, size=size)
                    cls._font_cache[key] = f
                    return f
                except Exception:
                    continue

        fallback = ImageFont.load_default()
        cls._font_cache[key] = fallback
        return fallback
