"""Integration tests for Phase 14 ecosystem adapters: Altair charts, HTML motion scenes, and Docling fallback."""

from __future__ import annotations

import json
from pathlib import Path

from upsc_studio.db.schemas import SceneSpec
from upsc_studio.integrations.altair_charts import AltairChartAdapter
from upsc_studio.integrations.docling_adapter import DoclingOCRAdapter
from upsc_studio.integrations.html_motion_exporter import HTMLMotionSceneExporter
from upsc_studio.integrations.registry import get_tool_registry


def test_altair_chart_adapter_exports_vegalite_and_html(tmp_path: Path) -> None:
    adapter = AltairChartAdapter()
    assert adapter.is_available() is True
    out = adapter.export_bar_chart(
        tmp_path,
        "SCN_03",
        "CPI Inflation vs Repo Rate (Illustrative)",
        [("FY22", 5.5), ("FY23", 6.7), ("FY24", 5.4)],
        x_label="Fiscal Year",
        y_label="Percent",
        source_label="RBI Annual Report",
    )
    vl = Path(out["vega_lite_json"])
    html = Path(out["interactive_html"])
    assert vl.exists() and html.exists()
    spec = json.loads(vl.read_text(encoding="utf-8"))
    assert "mark" in spec and "encoding" in spec


def test_html_motion_scene_exporter(tmp_path: Path) -> None:
    scene = SceneSpec(
        scene_id="SCN_01",
        section_id="SEC_01",
        section_title="Fundamental Rights",
        learning_objective="Explain Part III",
        narration_text="Part III guarantees Fundamental Rights.",
        estimated_duration_sec=10.0,
        visual_category="Kinetic Typography",
        on_screen_title="Part III: Articles 12-35",
        on_screen_bullets=["Right to Equality (14-18)", "Right to Freedom (19-22)"],
        source_citations=["Constitution of India"],
    )
    html_path = HTMLMotionSceneExporter().export_scene_html(tmp_path, "Fundamental Rights", scene)
    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")
    assert "Part III: Articles 12-35" in content
    assert "@keyframes fadeSlide" in content


def test_docling_adapter_capability_and_fallback(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    adapter = DoclingOCRAdapter()
    res = adapter.extract_if_available(pdf)
    assert res["status"] in {"DOCLING_NOT_INSTALLED", "SUCCESS"}
    assert "fallback" in res["capabilities"]


def test_tool_registry_includes_discovered_tools() -> None:
    reg = get_tool_registry()
    names = {t["name"] for t in reg}
    assert {"FFmpeg", "ManimCommunity/manim", "QGIS", "Blender", "whisper.cpp", "OpenTimelineIO"}.issubset(names)
