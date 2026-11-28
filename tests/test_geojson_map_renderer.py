"""Tests for evidence-backed GeoJSON map rendering."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate
from upsc_studio.graphics.geojson_renderer import GeoJSONMapRenderer
from upsc_studio.graphics.rights import AssetRightsLedger
from upsc_studio.projects.manager import ProjectManager


def _feature_collection() -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "North Test Region"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [10.0, 10.0], [12.0, 10.0], [12.0, 12.0],
                        [10.0, 12.0], [10.0, 10.0]
                    ]],
                },
            },
            {
                "type": "Feature",
                "properties": {"name": "South Test River"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[10.5, 10.2], [11.0, 10.8], [11.5, 11.5]],
                },
            },
        ],
    }


def _renderer(tmp_path: Path) -> tuple[GeoJSONMapRenderer, str]:
    conn = init_db(tmp_path / "map.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(name="GeoJSON test", chapter_title="Test geography", content_category="deep_dive")
    )
    rights = AssetRightsLedger(conn, Path(project.root_dir))
    return GeoJSONMapRenderer(Path(project.root_dir), rights), project.id


def test_geojson_map_renderer_draws_supplied_geometry_and_registers_asset(tmp_path: Path) -> None:
    renderer, project_id = _renderer(tmp_path)
    output = renderer.render(
        project_id=project_id,
        scene_id="SCN_MAP_01",
        title="Supplied test geography",
        geojson=_feature_collection(),
        source_citation="Test Gazetteer — map appendix",
        source_url="https://example.org/map-source",
        reference_date="2026-01-01",
    )

    assert output.is_file()
    assert output.stat().st_size > 10000
    with Image.open(output) as image:
        assert image.size == (1920, 1080)
        image.verify()


def test_geojson_map_rejects_missing_source_or_reference_date(tmp_path: Path) -> None:
    renderer, project_id = _renderer(tmp_path)
    with pytest.raises(ValueError, match="source title and URL"):
        renderer.render(
            project_id, "SCN_MAP_02", "Map without source", _feature_collection(),
            "", "", reference_date="2026-01-01"
        )
    with pytest.raises(ValueError, match="reference date/version"):
        renderer.render(
            project_id, "SCN_MAP_03", "Map without date", _feature_collection(),
            "Source title", "https://example.org/map-source"
        )


def test_geojson_map_rejects_unnamed_features_instead_of_inventing_legend_labels(tmp_path: Path) -> None:
    renderer, project_id = _renderer(tmp_path)
    data = _feature_collection()
    data["features"][0]["properties"] = {}

    with pytest.raises(ValueError, match="human-readable name"):
        renderer.render(
            project_id, "SCN_MAP_04", "Unnamed feature map", data,
            "Source title", "https://example.org/map-source", reference_date="2026-01-01"
        )


def test_geojson_map_rejects_out_of_range_coordinates(tmp_path: Path) -> None:
    renderer, project_id = _renderer(tmp_path)
    data = _feature_collection()
    data["features"][0]["geometry"]["coordinates"][0][1] = [300.0, 10.0]

    with pytest.raises(ValueError, match="WGS84 ranges"):
        renderer.render(
            project_id, "SCN_MAP_05", "Invalid geometry map", data,
            "Source title", "https://example.org/map-source", reference_date="2026-01-01"
        )
