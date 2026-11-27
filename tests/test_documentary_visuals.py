"""Acceptance and regression tests for documentary visual direction and animation engine.

Verifies:
- Pedagogically grounded visual type selection
- WCAG AA color contrast accessibility
- Evidence-backed data charts with traceability validation
- Landscape (16:9) and Vertical Shorts (9:16) dimensional accuracy
- SHA-256 asset caching and resumability
- Real MP4 rendering across all 10 documentary animation components
- Storyboard director visual direction plan generation
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image
import pytest

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate
from upsc_studio.graphics.design_system import (
    ColorPalette,
    LayoutOrientation,
    calculate_contrast_ratio,
    verify_wcag_aa,
)
from upsc_studio.graphics.documentary_animations import DocumentaryAnimationSuite
from upsc_studio.graphics.evidence_graphics import EvidenceGraphicsGenerator
from upsc_studio.graphics.rights import AssetRightsLedger
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.storyboard.director import StoryboardDirector
from upsc_studio.storyboard.visual_director import VisualDirectionEngine, VisualType


def test_visual_direction_engine_selection() -> None:
    """The VisualDirectionEngine must match sections to their appropriate educational visual form."""
    engine = VisualDirectionEngine()

    # Timeline match
    dec_timeline = engine.determine_visual(
        scene_id="SCN_01",
        section_id="SEC_01",
        title="Historical Evolution of Rights",
        objective="Understand the chronological timeline from Magna Carta to 1950",
        narration="In the 18th century and later in 1928 Nehru Report, evolution of constitutional guarantees took shape.",
    )
    assert dec_timeline.visual_type == VisualType.HISTORICAL_TIMELINE

    # Geographic Map match
    dec_map = engine.determine_visual(
        scene_id="SCN_02",
        section_id="SEC_02",
        title="River Basins and Himalayan Watersheds",
        objective="Trace spatial terrain boundaries and monsoon rainfall corridors",
        narration="The river basin extends across the peninsular plateau and northern boundary terrain.",
    )
    assert dec_map.visual_type == VisualType.GEOGRAPHICAL_MAP

    # Data Visualisation match
    dec_data = engine.determine_visual(
        scene_id="SCN_03",
        section_id="SEC_03",
        title="Fiscal Deficit and GDP Growth Trends",
        objective="Analyze statistical indicators from the Economic Survey",
        narration="The fiscal deficit share was recorded at 5.6% of GDP with revenue expenditure trends.",
    )
    assert dec_data.visual_type == VisualType.DATA_VISUALISATION

    # Split Comparison match
    dec_split = engine.determine_visual(
        scene_id="SCN_04",
        section_id="SEC_04",
        title="Pre-Reform vs Post-Reform Governance",
        objective="Evaluate challenges and reforms in public sector administration",
        narration="A comparison between the old regulatory hurdles versus the new streamlined single-window clearance.",
    )
    assert dec_split.visual_type == VisualType.SPLIT_COMPARISON

    # Institutional Diagram match
    dec_inst = engine.determine_visual(
        scene_id="SCN_05",
        section_id="SEC_05",
        title="Constitutional Separation of Powers",
        objective="Examine institutional jurisdictional oversight between judiciary and parliament",
        narration="The supreme court exercises oversight on executive commission mandates.",
    )
    assert dec_inst.visual_type == VisualType.INSTITUTIONAL_DIAGRAM


def test_design_system_contrast_and_accessibility() -> None:
    """All typography and background color combinations must satisfy WCAG AA contrast."""
    # Normal text on dark background (requires >= 4.5:1)
    ratio_primary = calculate_contrast_ratio(ColorPalette.TEXT_PRIMARY, ColorPalette.BG_DARK)
    assert ratio_primary >= 12.0
    assert verify_wcag_aa(ColorPalette.TEXT_PRIMARY, ColorPalette.BG_DARK, is_large_text=False)

    # Primary text on slate card surface (requires >= 4.5:1)
    ratio_card = calculate_contrast_ratio(ColorPalette.TEXT_PRIMARY, ColorPalette.SURFACE_CARD)
    assert ratio_card >= 9.0
    assert verify_wcag_aa(ColorPalette.TEXT_PRIMARY, ColorPalette.SURFACE_CARD, is_large_text=False)

    # Headline Gold accent on dark background (large text requires >= 3.0:1)
    assert verify_wcag_aa(ColorPalette.ACCENT_GOLD, ColorPalette.BG_DARK, is_large_text=True)

    # Sky Blue accent on dark background (large text requires >= 3.0:1)
    assert verify_wcag_aa(ColorPalette.ACCENT_SKY, ColorPalette.BG_DARK, is_large_text=True)


def test_evidence_data_chart_traceability_rejection(tmp_path: Path) -> None:
    """Data charts must fail validation if source, ref_period, or units are omitted."""
    conn = init_db(tmp_path / "chart.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(name="Data Test", chapter_title="Economic Growth")
    )
    rights = AssetRightsLedger(conn, Path(project.root_dir))
    gfx = EvidenceGraphicsGenerator(Path(project.root_dir), rights)

    # Missing source_label must raise ValueError
    with pytest.raises(ValueError, match="source_label is required"):
        gfx.render_data_chart(
            project_id=project.id,
            scene_id="SCN_01",
            title="Inflation Trends",
            bars=[("2022", 6.7), ("2023", 5.4)],
            unit="%",
            source_label="",
            ref_period="2022-2024",
        )

    # Missing unit must raise ValueError
    with pytest.raises(ValueError, match="unit of measurement is required"):
        gfx.render_data_chart(
            project_id=project.id,
            scene_id="SCN_01",
            title="Inflation Trends",
            bars=[("2022", 6.7), ("2023", 5.4)],
            unit="",
            source_label="MoSPI CPI Report",
            ref_period="2022-2024",
        )


def test_evidence_data_chart_landscape_and_vertical_rendering(tmp_path: Path) -> None:
    """Render verified data charts in both 16:9 landscape and 9:16 vertical shorts layouts."""
    conn = init_db(tmp_path / "chart_render.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(name="Render Test", chapter_title="Renewable Energy Capacity")
    )
    rights = AssetRightsLedger(conn, Path(project.root_dir))
    gfx = EvidenceGraphicsGenerator(Path(project.root_dir), rights)

    bars = [("Solar Energy", 72.0), ("Wind Power", 44.5), ("Biomass", 10.8), ("Small Hydro", 4.9)]

    # 1. Landscape 16:9
    p_landscape = gfx.render_data_chart(
        project_id=project.id,
        scene_id="SCN_01_LANDSCAPE",
        title="India Installed Renewable Capacity",
        bars=bars,
        unit="GW",
        source_label="Ministry of New and Renewable Energy (MNRE)",
        ref_period="2024",
        orientation=LayoutOrientation.LANDSCAPE_16_9,
    )
    assert p_landscape.exists()
    with Image.open(p_landscape) as img:
        assert img.size == (1920, 1080)

    # 2. Vertical 9:16 Shorts
    p_vertical = gfx.render_data_chart(
        project_id=project.id,
        scene_id="SCN_01_VERTICAL",
        title="Renewable Energy Mix",
        bars=bars,
        unit="GW",
        source_label="MNRE Official Dashboard",
        ref_period="2024",
        orientation=LayoutOrientation.VERTICAL_9_16,
    )
    assert p_vertical.exists()
    with Image.open(p_vertical) as img:
        assert img.size == (1080, 1920)


def test_caching_and_resumability(tmp_path: Path) -> None:
    """Rendering with identical parameters must return cached asset without re-drawing."""
    conn = init_db(tmp_path / "cache.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(name="Cache Test", chapter_title="Fiscal Indicators")
    )
    rights = AssetRightsLedger(conn, Path(project.root_dir))
    gfx = EvidenceGraphicsGenerator(Path(project.root_dir), rights)

    bars = [("Direct Tax", 54.0), ("Indirect Tax", 46.0)]
    path1 = gfx.render_data_chart(
        project_id=project.id,
        scene_id="SCN_CACHE",
        title="Gross Tax Revenue Share",
        bars=bars,
        unit="%",
        source_label="Union Budget Estimates",
        ref_period="2024-25",
    )
    mtime1 = path1.stat().st_mtime_ns

    # Call again with identical data
    path2 = gfx.render_data_chart(
        project_id=project.id,
        scene_id="SCN_CACHE",
        title="Gross Tax Revenue Share",
        bars=bars,
        unit="%",
        source_label="Union Budget Estimates",
        ref_period="2024-25",
    )
    assert path1 == path2
    assert path2.stat().st_mtime_ns == mtime1


def test_all_10_documentary_animation_components(tmp_path: Path) -> None:
    """Verify that all 10 documentary animation components render real, playable MP4 clips."""
    conn = init_db(tmp_path / "anim.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(name="Anim Suite Test", chapter_title="Constitutional & Ecological Systems")
    )
    rights = AssetRightsLedger(conn, Path(project.root_dir))
    suite = DocumentaryAnimationSuite(Path(project.root_dir), rights)

    # 1. Timeline Progression
    p1 = suite.render_timeline_progression(
        project.id, "ANIM_01", "Evolution of Environmental Protection",
        [("1972", "Stockholm Conference"), ("1986", "Environment Protection Act"), ("2010", "NGT Act")],
        "MoEFCC Gazette", duration_sec=1.5,
    )
    assert p1.exists() and p1.stat().st_size > 5000

    # 2. Cause and Effect
    p2 = suite.render_cause_and_effect(
        project.id, "ANIM_02", "Groundwater Depletion Mechanism",
        "Subsidized power and tubewell saturation",
        "Pumping exceeds aquifer recharge rate",
        "Salinization and critical water stress",
        "Central Ground Water Board (CGWB) Report", duration_sec=1.5,
    )
    assert p2.exists() and p2.stat().st_size > 5000

    # 3. Process Demonstration
    p3 = suite.render_process_demonstration(
        project.id, "ANIM_03", "Constitutional Amendment (Art. 368)",
        ["Introduction in either House", "Special Majority in both Houses", "Presidential Assent"],
        "Constitution of India Art. 368", duration_sec=1.5,
    )
    assert p3.exists() and p3.stat().st_size > 5000

    # 4. Flow Diagram
    p4 = suite.render_flow_diagram(
        project.id, "ANIM_04", "Tenth Schedule Disqualification Test",
        "Has legislator voluntarily given up party membership?",
        "Disqualification applies under Para 2(1)(a)",
        "No disqualification under statutory exception",
        "Tenth Schedule / Kihoto Hollohan", duration_sec=1.5,
    )
    assert p4.exists() and p4.stat().st_size > 5000

    # 5. Institutional Relationship
    p5 = suite.render_institutional_relationship(
        project.id, "ANIM_05", "Tripartite Institutional Balance",
        [("Executive", "Nodal Implementation"), ("Parliament", "Legislative Sanction"), ("Judiciary", "Judicial Review")],
        "Constitutional Matrix", duration_sec=1.5,
    )
    assert p5.exists() and p5.stat().st_size > 5000

    # 6. Map-Based Explanation
    p6 = suite.render_map_explanation(
        project.id, "ANIM_06", "Agro-Climatic Zones of India",
        [("Trans-Gangetic Plains", "High irrigation intensity"), ("Western Dry Region", "Arid climatic regime")],
        "ICAR Agro-Climatic Atlas", duration_sec=1.5,
    )
    assert p6.exists() and p6.stat().st_size > 5000

    # 7. Statistical Comparison
    p7 = suite.render_statistical_comparison(
        project.id, "ANIM_07", "Female Labour Force Participation",
        ("Rural FLFPR", 41.5), ("Urban FLFPR", 25.4),
        "%", "Periodic Labour Force Survey (PLFS) 2023-24", duration_sec=1.5,
    )
    assert p7.exists() and p7.stat().st_size > 5000

    # 8. Before-and-After Comparison
    p8 = suite.render_before_after_comparison(
        project.id, "ANIM_08", "Insolvency and Bankruptcy Code Impact",
        ["Average resolution took 4.3 years", "Recovery rate was ~26%"],
        ["Average resolution reduced to 330 days", "Recovery rate improved to ~38%"],
        "Insolvency and Bankruptcy Board of India (IBBI)", duration_sec=1.5,
    )
    assert p8.exists() and p8.stat().st_size > 5000

    # 9. Scientific Process
    p9 = suite.render_scientific_process(
        project.id, "ANIM_09", "Photovoltaic Electricity Generation",
        "Solar photons striking silicon semiconductor",
        "Electron-hole pair separation across p-n junction",
        "Direct electric current generated",
        "NCERT Physics Class XII", duration_sec=1.5,
    )
    assert p9.exists() and p9.stat().st_size > 5000

    # 10. Historical Changes
    p10 = suite.render_historical_changes(
        project.id, "ANIM_10", "Evolution of Federal Fiscal Transfers",
        ("Pre-14th Finance Commission", "Discretionary plan grants dominated transfers"),
        ("Post-14th Finance Commission", "Untied tax devolution increased to 42%"),
        "Finance Commission of India Reports", duration_sec=1.5,
    )
    assert p10.exists() and p10.stat().st_size > 5000


def test_storyboard_director_integrates_visual_direction_plan(tmp_path: Path) -> None:
    """StoryboardDirector must generate visual_direction_plan.json alongside storyboard.json."""
    director = StoryboardDirector(tmp_path)
    sections = [
        {
            "section_id": "SEC_01",
            "title": "Historical Context of Fundamental Rights",
            "objective": "Trace the chronological evolution of constitutional rights",
            "narration": "From the Nehru Report of 1928 to the Constituent Assembly debates, fundamental rights developed.",
            "duration_sec": 120,
            "visual_category": "Historical Timeline",
            "claim_ids": ["clm_01"],
        },
        {
            "section_id": "SEC_02",
            "title": "Procedural Mechanism of Article 32 Writs",
            "objective": "Explain the step by step procedure of writ petitions",
            "narration": "The citizen approaches the supreme court directly under Article 32 when rights are violated.",
            "duration_sec": 140,
            "visual_category": "Process Animation",
            "claim_ids": ["clm_02"],
        },
    ]

    scenes = director.build_storyboard("Fundamental Rights", sections)
    assert len(scenes) == 2

    # Check metadata in scenes
    assert scenes[0].metadata["visual_type"] == VisualType.HISTORICAL_TIMELINE.value
    assert scenes[1].metadata["visual_type"] == VisualType.PROCESS_ANIMATION.value

    # Check generated files
    sb_dir = tmp_path / "storyboard"
    assert (sb_dir / "storyboard.json").exists()
    assert (sb_dir / "visual_direction_plan.json").exists()
    assert (sb_dir / "graphics_spec.json").exists()
    assert (sb_dir / "transition_plan.json").exists()
