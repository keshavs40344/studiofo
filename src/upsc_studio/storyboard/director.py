"""Scene-by-scene storyboard and transition planning engine."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from upsc_studio.db.schemas import RightsStatus, SceneSpec


class StoryboardDirector:
    """Converts teaching script sections into source-linked, purposeful visual scenes."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.storyboard_dir = project_dir / "storyboard"
        self.storyboard_dir.mkdir(parents=True, exist_ok=True)

    def build_storyboard(self, chapter_title: str, sections: list[dict]) -> list[SceneSpec]:
        """Generate scene specs, graphics specs, and transition plan from script sections."""
        scenes: list[SceneSpec] = []
        graphics_specs: list[dict] = []
        transitions: list[dict] = []

        for idx, sec in enumerate(sections, start=1):
            scene_id = f"SCN_{idx:02d}"
            bullets = self._extract_bullets(sec["narration"])
            trans_in = "fade_in" if idx == 1 else "cross_dissolve"
            trans_out = "dip_to_black" if idx == len(sections) else "hard_cut"
            anim = "zoom_in" if idx == 1 else ("step_reveal" if "Flowchart" in sec["visual_category"] else "fade_in")

            scene = SceneSpec(
                scene_id=scene_id,
                section_id=sec["section_id"],
                section_title=sec["title"],
                learning_objective=sec["objective"],
                narration_text=sec["narration"],
                claim_ids=sec.get("claim_ids", []),
                estimated_duration_sec=float(sec["duration_sec"]),
                visual_category=sec["visual_category"],
                primary_asset=None,
                asset_rights_status=RightsStatus.ORIGINAL_GENERATED,
                on_screen_title=f"{sec['section_id']}: {sec['title']}",
                on_screen_bullets=bullets,
                animation_type=anim,
                transition_in=trans_in,
                transition_out=trans_out,
                audio_cue="narration_only" if idx > 1 else "intro_soft_ducked",
                source_citations=[f"Claim {cid}" for cid in sec.get("claim_ids", [])] or ["Conceptual Framework"],
                qc_status="PENDING",
            )
            scenes.append(scene)
            graphics_specs.append(
                {
                    "scene_id": scene_id,
                    "visual_category": sec["visual_category"],
                    "title": sec["title"],
                    "subtitle": chapter_title,
                    "bullets": bullets,
                    "citation": ", ".join(scene.source_citations),
                }
            )
            transitions.append(
                {
                    "scene_id": scene_id,
                    "in": trans_in,
                    "out": trans_out,
                    "purpose": "Logical section progression without distracting effects",
                    "duration_sec": 0.4,
                }
            )

        (self.storyboard_dir / "storyboard.json").write_text(
            json.dumps([s.model_dump() for s in scenes], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.storyboard_dir / "graphics_spec.json").write_text(
            json.dumps(graphics_specs, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.storyboard_dir / "transition_plan.json").write_text(
            json.dumps(transitions, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.storyboard_dir / "visual_asset_requests.json").write_text(
            json.dumps(
                [
                    {
                        "scene_id": s.scene_id,
                        "required_type": s.visual_category,
                        "fallback": "Original generated 1080p vector/Pillow educational graphic",
                    }
                    for s in scenes
                ],
                indent=2,
            ),
            encoding="utf-8",
        )
        checklist = [
            f"# Visual QA Checklist — {chapter_title}",
            "",
            *[
                f"- [ ] **{s.scene_id}** ({s.visual_category}): Objective='{s.learning_objective}' | Citations={s.source_citations}"
                for s in scenes
            ],
        ]
        (self.storyboard_dir / "visual_qa_checklist.md").write_text("\n".join(checklist), encoding="utf-8")
        return scenes

    @staticmethod
    def _extract_bullets(narration: str) -> list[str]:
        parts = [p.strip() for p in narration.split(".") if len(p.strip()) >= 15]
        return [textwrap.shorten(p, width=90, placeholder="...") for p in parts[:4]]
