"""Evidence-aware scene and asset audit for documentary visual QA.

This module performs deterministic structural checks only. It does not claim to
understand image semantics; semantic relevance still requires a current human review.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from PIL import Image

from upsc_studio.db.schemas import SceneSpec


_PLACEHOLDER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ELEMENT_NUMBER", re.compile(r"\belement\s+\d+\b", re.IGNORECASE)),
    ("GENERIC_DIMENSION", re.compile(r"\bdimension\s+[ab]\b", re.IGNORECASE)),
    ("CONCEPTUAL_FRAMEWORK_FALLBACK", re.compile(r"\bconceptual framework\b", re.IGNORECASE)),
    ("SOURCE_CITATION_PENDING", re.compile(r"\bsource (?:citation|attribution) pending\b", re.IGNORECASE)),
    ("PLACEHOLDER_TOKEN", re.compile(r"\b(?:placeholder|lorem ipsum|insert here|todo)\b", re.IGNORECASE)),
    ("GENERIC_NAME_TOKEN", re.compile(r"^\s*\+?\s*name\s*$", re.IGNORECASE)),
    ("GENERIC_DATE_TOKEN", re.compile(r"^\s*date\s*$", re.IGNORECASE)),
    ("GENERIC_LABEL_TOKEN", re.compile(r"^\s*label\s*$", re.IGNORECASE)),
)

_REQUIRED_SPECIALIZED_TYPES = {
    "HISTORICAL_TIMELINE": "TIMELINE",
    "GEOGRAPHICAL_MAP": "GEOGRAPHIC_MAP",
    "DATA_VISUALISATION": "DATA_CHART",
    "STATISTICAL_COMPARISON": "DATA_CHART",
    "INSTITUTIONAL_DIAGRAM": "INSTITUTIONAL_RELATIONSHIP_DIAGRAM",
    "FLOWCHART": "FLOWCHART",
    "STEP_BY_STEP_MECHANISM": "FLOWCHART",
    "SCIENTIFIC_ILLUSTRATION": "SCIENTIFIC_PROCESS",
    "CAUSE_AND_EFFECT": "CAUSE_EFFECT",
    "SPLIT_COMPARISON": "BEFORE_AFTER_COMPARISON",
    "BEFORE_AFTER": "BEFORE_AFTER_COMPARISON",
}


def _scene_text_fields(scene: SceneSpec) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = [
        ("section_title", scene.section_title),
        ("learning_objective", scene.learning_objective),
        ("narration_text", scene.narration_text),
        ("on_screen_title", scene.on_screen_title),
    ]
    fields.extend((f"on_screen_bullets[{index}]", value) for index, value in enumerate(scene.on_screen_bullets))
    fields.extend((f"source_citations[{index}]", value) for index, value in enumerate(scene.source_citations))
    return fields


def audit_documentary_scenes(scenes: list[SceneSpec]) -> dict[str, Any]:
    """Check assets, placeholders, evidence metadata and requested/rendered visual types."""
    blockers: list[str] = []
    warnings: list[str] = []
    scene_results: list[dict[str, Any]] = []

    if not scenes:
        blockers.append("No storyboard scenes were supplied for visual QA.")

    for scene in scenes:
        scene_blockers: list[str] = []
        scene_warnings: list[str] = []
        metadata = scene.metadata or {}
        visual_type = str(metadata.get("visual_type") or "").upper()
        rendered_kind = str(metadata.get("rendered_visual_kind") or "").upper()

        for field_name, value in _scene_text_fields(scene):
            text = str(value or "")
            for code, pattern in _PLACEHOLDER_PATTERNS:
                if pattern.search(text):
                    scene_blockers.append(f"{scene.scene_id}: placeholder {code} found in {field_name}.")

        asset_value = str(scene.primary_asset or "").strip()
        if not asset_value:
            scene_blockers.append(f"{scene.scene_id}: primary visual asset is missing.")
        else:
            asset = Path(asset_value)
            if not asset.is_file():
                scene_blockers.append(f"{scene.scene_id}: visual asset does not exist: {asset.name}.")
            elif asset.stat().st_size <= 0:
                scene_blockers.append(f"{scene.scene_id}: visual asset is empty: {asset.name}.")
            elif asset.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                try:
                    with Image.open(asset) as image:
                        image.verify()
                except Exception as exc:
                    scene_blockers.append(
                        f"{scene.scene_id}: image asset is not a valid decodable image ({type(exc).__name__})."
                    )
            elif asset.suffix.lower() not in {".mp4", ".mov", ".mkv"}:
                scene_blockers.append(
                    f"{scene.scene_id}: unsupported visual asset type {asset.suffix or '[no extension]'}."
                )

        expected_kind = _REQUIRED_SPECIALIZED_TYPES.get(visual_type)
        if expected_kind and rendered_kind != expected_kind:
            scene_blockers.append(
                f"{scene.scene_id}: requested {visual_type} but rendered visual kind is "
                f"{rendered_kind or 'UNSPECIFIED'}; expected {expected_kind}."
            )

        visual_warning = str(metadata.get("visual_data_warning") or "").strip()
        if visual_warning:
            scene_blockers.append(f"{scene.scene_id}: {visual_warning}")

        citation_records = metadata.get("citation_records")
        if scene.claim_ids and metadata.get("citation_status") != "VERIFIED_EXTERNAL_SOURCE_LINKED":
            scene_blockers.append(
                f"{scene.scene_id}: factual claim IDs are not linked to verified external source records."
            )
        if expected_kind:
            if not isinstance(citation_records, list) or not citation_records:
                scene_blockers.append(
                    f"{scene.scene_id}: specialised factual visual has no linked external citation records."
                )
            else:
                for record_index, record in enumerate(citation_records):
                    if not isinstance(record, dict):
                        scene_blockers.append(
                            f"{scene.scene_id}: citation record {record_index + 1} is malformed."
                        )
                        continue
                    required = ("title", "publisher", "url", "source_tier")
                    missing = [key for key in required if not str(record.get(key) or "").strip()]
                    if missing:
                        scene_blockers.append(
                            f"{scene.scene_id}: citation record {record_index + 1} lacks {', '.join(missing)}."
                        )
                    if str(record.get("source_tier", "")).upper() == "USER_NOTES":
                        scene_blockers.append(
                            f"{scene.scene_id}: user notes cannot be represented as an external source citation."
                        )

        if metadata.get("rendered_visual_kind") == "GENERIC_PROCESS_FALLBACK":
            scene_blockers.append(
                f"{scene.scene_id}: generic process fallback does not satisfy the requested specialist visual."
            )

        blockers.extend(scene_blockers)
        warnings.extend(scene_warnings)
        scene_results.append(
            {
                "scene_id": scene.scene_id,
                "requested_visual_type": visual_type or None,
                "rendered_visual_kind": rendered_kind or None,
                "asset": asset_value or None,
                "blockers": scene_blockers,
                "warnings": scene_warnings,
            }
        )

    return {
        "status": "FAILED" if blockers else "PASSED",
        "scenes_audited": len(scenes),
        "blockers": blockers,
        "warnings": warnings,
        "scene_results": scene_results,
        "semantic_visual_relevance": "HUMAN_REVIEW_REQUIRED",
        "limitations": [
            "This audit checks structure, provenance metadata, placeholders, and decodable image assets.",
            "It does not certify that an image depicts the correct subject or that a map is geographically accurate.",
            "Final semantic relevance and full-video playback require a current human review.",
        ],
    }
