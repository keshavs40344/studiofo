"""Scene-by-scene storyboard and transition planning engine."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from upsc_studio.db.schemas import RightsStatus, SceneSpec
from upsc_studio.storyboard.visual_director import VisualDirectionEngine


class StoryboardDirector:
    """Converts teaching script sections into source-linked, purposeful visual scenes."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.storyboard_dir = project_dir / "storyboard"
        self.storyboard_dir.mkdir(parents=True, exist_ok=True)

    def _expand_sections_to_beats(self, sections: list[dict]) -> list[dict]:
        """Split long narrative sections into crisp 15-25s documentary beats."""
        import re
        beats: list[dict] = []
        for sec in sections:
            narration = str(sec.get("narration", "")).strip()
            words = narration.split()
            sentences = [s.strip() for s in re.split(r"(?<=[.!?।])\s+|\n+", narration) if len(s.strip()) >= 12]
            if len(words) <= 55 or len(sentences) < 3:
                beats.append(sec)
                continue
            # Group into 2-sentence beats so each scene stays dynamic (12-25s)
            chunk_size = 2
            chunks = [sentences[i : i + chunk_size] for i in range(0, len(sentences), chunk_size)]
            total_dur = float(sec.get("duration_sec", 20.0))
            total_len = max(1, sum(len(" ".join(c).split()) for c in chunks))
            for b_idx, chunk in enumerate(chunks, start=1):
                beat_text = " ".join(chunk)
                beat_words = len(beat_text.split())
                beat_dur = max(6.0, round(total_dur * (beat_words / total_len), 1))
                beats.append({
                    **sec,
                    "title": f"{sec['title']} (Part {b_idx})" if len(chunks) > 1 else sec["title"],
                    "narration": beat_text,
                    "duration_sec": beat_dur,
                })
        return beats

    def build_storyboard(self, chapter_title: str, sections: list[dict]) -> list[SceneSpec]:
        """Generate scene specs, graphics specs, and transition plan from script sections."""
        scenes: list[SceneSpec] = []
        graphics_specs: list[dict] = []
        transitions: list[dict] = []
        visual_plan: list[dict] = []
        director_engine = VisualDirectionEngine()
        beats = self._expand_sections_to_beats(sections)

        for idx, sec in enumerate(beats, start=1):
            scene_id = f"SCN_{idx:02d}"
            bullets = self._extract_bullets(sec["narration"])
            trans_in = "fade_in" if idx == 1 else "cross_dissolve"
            trans_out = "dip_to_black" if idx == len(beats) else "hard_cut"
            anim = "zoom_in" if idx == 1 else ("step_reveal" if "Flowchart" in sec["visual_category"] else "fade_in")

            decision = director_engine.determine_visual(
                scene_id=scene_id,
                section_id=sec["section_id"],
                title=sec["title"],
                objective=sec.get("objective", ""),
                narration=sec.get("narration", ""),
                visual_category=sec.get("visual_category", ""),
            )
            visual_plan.append(decision.to_dict())

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
                metadata={
                    "visual_type": decision.visual_type.value,
                    "teaching_rationale": decision.rationale,
                    "recommended_animation": decision.recommended_animation,
                },
            )
            scenes.append(scene)
            graphics_specs.append(
                {
                    "scene_id": scene_id,
                    "visual_category": sec["visual_category"],
                    "visual_type": decision.visual_type.value,
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
        (self.storyboard_dir / "visual_direction_plan.json").write_text(
            json.dumps(visual_plan, indent=2, ensure_ascii=False),
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
