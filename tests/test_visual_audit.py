"""Regression tests for documentary scene visual QA and fail-closed placeholders."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from upsc_studio.db.schemas import RightsStatus, SceneSpec
from upsc_studio.graphics.documentary_animations import DocumentaryAnimationSuite
from upsc_studio.qa.visual_audit import audit_documentary_scenes


def _scene(asset: Path, **metadata) -> SceneSpec:
    return SceneSpec(
        scene_id="SCN_01",
        section_id="SEC_01",
        section_title="A topic-specific scene",
        learning_objective="Explain the actual concept",
        narration_text="The scene explains the topic using a source-linked visual.",
        claim_ids=["claim-01"],
        estimated_duration_sec=8.0,
        visual_category="Historical Timeline",
        primary_asset=str(asset),
        asset_rights_status=RightsStatus.ORIGINAL_GENERATED,
        on_screen_title="A topic-specific scene",
        on_screen_bullets=["First sourced event", "Second sourced event"],
        source_citations=["Official source — section 2"],
        metadata={
            "visual_type": "HISTORICAL_TIMELINE",
            "rendered_visual_kind": "TIMELINE",
            "citation_status": "VERIFIED_EXTERNAL_SOURCE_LINKED",
            "citation_records": [
                {
                    "claim_id": "claim-01",
                    "title": "Official historical record",
                    "publisher": "Public Authority",
                    "url": "https://example.org/source",
                    "page_or_section": "Section 2",
                    "source_tier": "PRIMARY_OFFICIAL",
                }
            ],
            **metadata,
        },
    )


def test_visual_audit_accepts_structurally_valid_scene_but_requires_human_semantic_review(tmp_path: Path) -> None:
    image_path = tmp_path / "timeline.png"
    Image.new("RGB", (640, 360), "navy").save(image_path)

    result = audit_documentary_scenes([_scene(image_path)])

    assert result["status"] == "PASSED"
    assert result["scenes_audited"] == 1
    assert result["semantic_visual_relevance"] == "HUMAN_REVIEW_REQUIRED"
    assert result["blockers"] == []


def test_visual_audit_blocks_placeholder_labels(tmp_path: Path) -> None:
    image_path = tmp_path / "timeline.png"
    Image.new("RGB", (640, 360), "navy").save(image_path)
    scene = _scene(image_path, rendered_visual_kind="TIMELINE")
    scene.on_screen_bullets = ["Element 1", "Second sourced event"]

    result = audit_documentary_scenes([scene])

    assert result["status"] == "FAILED"
    assert any("ELEMENT_NUMBER" in item for item in result["blockers"])


def test_visual_audit_blocks_region_cards_misrepresented_as_geographic_map(tmp_path: Path) -> None:
    image_path = tmp_path / "regions.png"
    Image.new("RGB", (640, 360), "navy").save(image_path)
    scene = _scene(
        image_path,
        visual_type="GEOGRAPHICAL_MAP",
        rendered_visual_kind="REGION_CARDS_NOT_GEOGRAPHIC_MAP",
        visual_data_warning="The current renderer produces region cards, not a geographic map.",
    )

    result = audit_documentary_scenes([scene])

    assert result["status"] == "FAILED"
    assert any("expected GEOGRAPHIC_MAP" in item for item in result["blockers"])
    assert any("region cards" in item.lower() for item in result["blockers"])


def test_visual_audit_blocks_missing_assets_and_source_provenance(tmp_path: Path) -> None:
    scene = _scene(tmp_path / "missing.png")
    scene.metadata["citation_records"] = []

    result = audit_documentary_scenes([scene])

    assert result["status"] == "FAILED"
    assert any("does not exist" in item for item in result["blockers"])
    assert any("citation records" in item for item in result["blockers"])


def test_animation_components_do_not_insert_sample_data_when_input_is_missing(tmp_path: Path) -> None:
    suite = DocumentaryAnimationSuite(tmp_path, rights_ledger=object())

    import pytest

    with pytest.raises(ValueError, match="two sourced milestones"):
        suite.render_timeline_progression("p", "s1", "Timeline", [], "source")
    with pytest.raises(ValueError, match="at least one supplied step"):
        suite.render_process_demonstration("p", "s2", "Process", [], "source")
    with pytest.raises(ValueError, match="named, supplied institutions"):
        suite.render_institutional_relationship("p", "s3", "Institutions", [], "source")
    with pytest.raises(ValueError, match="two supplied, sourced regions"):
        suite.render_map_explanation("p", "s4", "Regions", [], "source")
