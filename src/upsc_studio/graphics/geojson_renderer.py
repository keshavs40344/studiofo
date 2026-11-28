"""Evidence-backed GeoJSON map renderer using supplied WGS84 geometries.

No geographic boundaries or locations are invented here. The caller must provide
a valid GeoJSON FeatureCollection and linked source attribution.
"""
from __future__ import annotations

import hashlib
import json
import math
import textwrap
from pathlib import Path
from typing import Any, Iterator

from PIL import Image, ImageDraw

from upsc_studio.graphics.design_system import ColorPalette, FontManager
from upsc_studio.graphics.rights import AssetRightsLedger
from upsc_studio.db.schemas import RightsStatus


def _positions(value: Any) -> Iterator[tuple[float, float]]:
    if (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        lon, lat = float(value[0]), float(value[1])
        if not (math.isfinite(lon) and math.isfinite(lat)):
            raise ValueError("GeoJSON coordinates must be finite numbers.")
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("GeoJSON coordinates must use longitude/latitude in WGS84 ranges.")
        yield lon, lat
        return
    if isinstance(value, (list, tuple)):
        for child in value:
            yield from _positions(child)


def _geometry_paths(geometry: dict[str, Any]) -> list[tuple[str, list[list[tuple[float, float]]]]]:
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, (list, tuple)):
        raise ValueError("GeoJSON geometry is missing coordinates.")

    paths: list[tuple[str, list[list[tuple[float, float]]]]] = []

    def ring_path(value: Any) -> list[tuple[float, float]]:
        coords = list(_positions(value))
        if len(coords) < 2:
            raise ValueError("GeoJSON line/polygon geometry needs at least two coordinates.")
        return coords

    if kind == "Point":
        point = next(_positions(coordinates), None)
        if point is None:
            raise ValueError("GeoJSON Point is empty.")
        paths.append(("Point", [[point]]))
    elif kind == "MultiPoint":
        points = list(_positions(coordinates))
        if not points:
            raise ValueError("GeoJSON MultiPoint is empty.")
        paths.append(("Point", [[point] for point in points]))
    elif kind == "LineString":
        paths.append(("LineString", [ring_path(coordinates)]))
    elif kind == "MultiLineString":
        paths.append(("LineString", [ring_path(line) for line in coordinates]))
    elif kind == "Polygon":
        paths.append(("Polygon", [ring_path(ring) for ring in coordinates]))
    elif kind == "MultiPolygon":
        for polygon in coordinates:
            paths.append(("Polygon", [ring_path(ring) for ring in polygon]))
    else:
        raise ValueError(f"Unsupported GeoJSON geometry type: {kind!r}.")
    return paths


class GeoJSONMapRenderer:
    """Render real supplied geographic geometry as an original educational map."""

    WIDTH = 1920
    HEIGHT = 1080
    PALETTE = (
        ColorPalette.ACCENT_GOLD,
        ColorPalette.ACCENT_SKY,
        ColorPalette.ACCENT_EMERALD,
        ColorPalette.ACCENT_ROSE,
        ColorPalette.ACCENT_PURPLE,
    )

    def __init__(self, project_dir: Path, rights_ledger: AssetRightsLedger) -> None:
        self.project_dir = Path(project_dir)
        self.out_dir = self.project_dir / "assets" / "generated" / "maps"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.rights_ledger = rights_ledger

    def render(
        self,
        project_id: str,
        scene_id: str,
        title: str,
        geojson: dict[str, Any],
        source_citation: str,
        source_url: str,
        reference_date: str | None = None,
    ) -> Path:
        if not isinstance(geojson, dict) or geojson.get("type") != "FeatureCollection":
            raise ValueError("A geographic map requires a GeoJSON FeatureCollection.")
        if not source_citation.strip() or not source_url.strip():
            raise ValueError("A geographic map requires a linked source title and URL.")

        features = geojson.get("features")
        if not isinstance(features, list) or not features:
            raise ValueError("GeoJSON FeatureCollection must contain at least one feature.")
        if len(features) > 12:
            raise ValueError("Map renderer supports at most 12 labelled features; split the map into topic-specific layers.")
        if not str(reference_date or "").strip():
            raise ValueError("A map reference date/version is required to establish the geographic data's time scope.")

        parsed: list[dict[str, Any]] = []
        all_points: list[tuple[float, float]] = []
        for index, feature in enumerate(features):
            if not isinstance(feature, dict) or feature.get("type") != "Feature":
                raise ValueError(f"GeoJSON feature {index + 1} is malformed.")
            geometry = feature.get("geometry")
            properties = feature.get("properties") or {}
            if not isinstance(geometry, dict) or not isinstance(properties, dict):
                raise ValueError(f"GeoJSON feature {index + 1} has invalid geometry/properties.")
            paths = _geometry_paths(geometry)
            feature_points = [point for _, path_list in paths for path in path_list for point in path]
            if not feature_points:
                raise ValueError(f"GeoJSON feature {index + 1} contains no usable coordinates.")
            all_points.extend(feature_points)
            feature_name = str(
                properties.get("name") or properties.get("name_en") or properties.get("label") or ""
            ).strip()
            if not feature_name:
                raise ValueError(
                    f"GeoJSON feature {index + 1} needs a human-readable name for the map legend."
                )
            parsed.append({"name": feature_name, "paths": paths})

        longitudes = [point[0] for point in all_points]
        latitudes = [point[1] for point in all_points]
        min_lon, max_lon = min(longitudes), max(longitudes)
        min_lat, max_lat = min(latitudes), max(latitudes)
        if max_lon - min_lon < 0.001 or max_lat - min_lat < 0.001:
            raise ValueError("Map geometry needs a non-zero geographic extent.")
        if max_lon - min_lon > 180:
            raise ValueError("Map geometry crosses the antimeridian or spans too widely; split the extent.")

        # Keep map geometry inside a dedicated panel; legend and attribution sit alongside/below.
        left, top, panel_w, panel_h = 110, 190, 1320, 690
        pad = 35
        span_lon = max_lon - min_lon
        span_lat = max_lat - min_lat
        scale = min((panel_w - 2 * pad) / span_lon, (panel_h - 2 * pad) / span_lat)
        draw_w = span_lon * scale
        draw_h = span_lat * scale
        offset_x = left + (panel_w - draw_w) / 2
        offset_y = top + (panel_h - draw_h) / 2

        def project(point: tuple[float, float]) -> tuple[int, int]:
            lon, lat = point
            x = offset_x + (lon - min_lon) * scale
            y = offset_y + (max_lat - lat) * scale
            return int(round(x)), int(round(y))

        canonical = json.dumps(geojson, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha256(
            f"{title}|{canonical}|{source_url}|{reference_date or ''}".encode("utf-8")
        ).hexdigest()[:16]
        output_path = self.out_dir / f"{scene_id}_geojson_{digest}.png"
        if output_path.is_file() and output_path.stat().st_size > 10000:
            return output_path

        image = Image.new("RGB", (self.WIDTH, self.HEIGHT), ColorPalette.BG_DARK)
        draw = ImageDraw.Draw(image)
        f_title = FontManager.get_font(54, bold=True)
        f_heading = FontManager.get_font(30, bold=True)
        f_body = FontManager.get_font(25, bold=False)
        f_meta = FontManager.get_font(18, bold=False)

        draw.rectangle([0, 0, self.WIDTH, 10], fill=ColorPalette.ACCENT_GOLD)
        draw.text((96, 62), "GEOGRAPHIC EXPLANATION  |  WGS84 / PLATE CARRÉE", fill=ColorPalette.ACCENT_SKY, font=f_meta)
        draw.text((96, 100), title, fill=ColorPalette.TEXT_PRIMARY, font=f_title)
        draw.rounded_rectangle(
            [left - 18, top - 18, left + panel_w + 18, top + panel_h + 18],
            radius=22,
            fill=ColorPalette.SURFACE_CARD,
            outline=ColorPalette.BORDER_SUBTLE,
            width=2,
        )

        for index, feature in enumerate(parsed):
            color = self.PALETTE[index % len(self.PALETTE)]
            for geometry_type, paths in feature["paths"]:
                for path in paths:
                    points = [project(point) for point in path]
                    if geometry_type == "Polygon":
                        if len(points) < 3:
                            raise ValueError("Polygon rings require at least three points.")
                        draw.polygon(points, fill=(45, 75, 91), outline=color)
                        draw.line(points + [points[0]], fill=color, width=3, joint="curve")
                    elif geometry_type == "LineString":
                        draw.line(points, fill=color, width=5, joint="curve")
                    elif geometry_type == "Point":
                        x, y = points[0]
                        draw.ellipse([x - 9, y - 9, x + 9, y + 9], fill=color, outline=ColorPalette.TEXT_PRIMARY, width=2)

        legend_x = 1510
        legend_y = 230
        draw.text((legend_x, legend_y), "MAP KEY", fill=ColorPalette.TEXT_PRIMARY, font=f_heading)
        for index, feature in enumerate(parsed[:12]):
            y = legend_y + 58 + index * 48
            color = self.PALETTE[index % len(self.PALETTE)]
            draw.ellipse([legend_x, y + 7, legend_x + 18, y + 25], fill=color)
            draw.text((legend_x + 32, y), feature["name"], fill=ColorPalette.TEXT_SECONDARY, font=f_body)

        extent_text = f"Lon {min_lon:.3f}° to {max_lon:.3f}°  |  Lat {min_lat:.3f}° to {max_lat:.3f}°"
        draw.text((left, 914), extent_text, fill=ColorPalette.TEXT_MUTED, font=f_meta)
        attribution = f"Source: {source_citation}  |  Reference date: {reference_date}"
        footer_lines = textwrap.wrap(attribution, width=125) or [attribution]
        if len(footer_lines) > 2 or any(draw.textlength(line, font=f_meta) > self.WIDTH - 2 * 96 for line in footer_lines):
            raise ValueError(
                "Map source attribution does not fit the footer; use a concise source title and keep full provenance in the ledger."
            )
        for line_index, line in enumerate(footer_lines):
            draw.text((96, 946 + line_index * 24), line, fill=ColorPalette.TEXT_MUTED, font=f_meta)
        draw.text((96, 996), "Projection: longitude/latitude plotted as Plate Carrée; not suitable for distance measurement.", fill=ColorPalette.TEXT_MUTED, font=f_meta)

        image.save(output_path, format="PNG")
        self.rights_ledger.register_asset(
            project_id=project_id,
            asset_type="geojson_map",
            file_path=output_path,
            creator="UPSC Studio GeoJSONMapRenderer",
            licence="ORIGINAL_GENERATED",
            rights_status=RightsStatus.ORIGINAL_GENERATED,
            attribution=f"Original map visualization from supplied GeoJSON. Source: {source_citation} ({source_url})",
        )
        return output_path
