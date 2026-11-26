"""Pure-Python OpenTimelineIO (OTIO Timeline.1) JSON exporter."""

from __future__ import annotations

import json
from pathlib import Path

from upsc_studio.db.schemas import SceneSpec


def export_otio_timeline(
    project_name: str,
    scenes: list[SceneSpec],
    narration_wav: Path | None,
    output_path: Path,
    fps: int = 30,
) -> Path:
    """Export an OpenTimelineIO-compatible Timeline.1 JSON file without C++ binary deps."""
    video_children: list[dict] = []
    for idx, scene in enumerate(scenes):
        duration_frames = max(1, int(round(scene.estimated_duration_sec * fps)))
        clip = {
            "OTIO_SCHEMA": "Clip.2",
            "name": f"{scene.scene_id}_{scene.section_title[:30]}",
            "media_reference": {
                "OTIO_SCHEMA": "ExternalReference.1",
                "target_url": Path(scene.primary_asset).as_uri() if scene.primary_asset else "",
            },
            "source_range": {
                "OTIO_SCHEMA": "TimeRange.1",
                "start_time": {"OTIO_SCHEMA": "RationalTime.1", "value": 0.0, "rate": float(fps)},
                "duration": {"OTIO_SCHEMA": "RationalTime.1", "value": float(duration_frames), "rate": float(fps)},
            },
            "metadata": {
                "upsc_studio": {
                    "scene_id": scene.scene_id,
                    "learning_objective": scene.learning_objective,
                    "claim_ids": scene.claim_ids,
                    "rights_status": scene.asset_rights_status.value,
                }
            },
        }
        video_children.append(clip)
        if idx < len(scenes) - 1 and scene.transition_out != "hard_cut":
            half_frames = max(1, int(round(0.2 * fps)))
            video_children.append(
                {
                    "OTIO_SCHEMA": "Transition.1",
                    "name": scene.transition_out,
                    "transition_type": "SMPTE_Dissolve",
                    "in_offset": {"OTIO_SCHEMA": "RationalTime.1", "value": float(half_frames), "rate": float(fps)},
                    "out_offset": {"OTIO_SCHEMA": "RationalTime.1", "value": float(half_frames), "rate": float(fps)},
                }
            )

    total_frames = sum(max(1, int(round(s.estimated_duration_sec * fps))) for s in scenes)
    audio_children: list[dict] = []
    if narration_wav and narration_wav.exists():
        audio_children.append(
            {
                "OTIO_SCHEMA": "Clip.2",
                "name": "User_Own_Voice_Narration",
                "media_reference": {
                    "OTIO_SCHEMA": "ExternalReference.1",
                    "target_url": narration_wav.resolve().as_uri(),
                },
                "source_range": {
                    "OTIO_SCHEMA": "TimeRange.1",
                    "start_time": {"OTIO_SCHEMA": "RationalTime.1", "value": 0.0, "rate": float(fps)},
                    "duration": {"OTIO_SCHEMA": "RationalTime.1", "value": float(total_frames), "rate": float(fps)},
                },
            }
        )

    otio_doc = {
        "OTIO_SCHEMA": "Timeline.1",
        "name": project_name,
        "global_start_time": {"OTIO_SCHEMA": "RationalTime.1", "value": 0.0, "rate": float(fps)},
        "tracks": {
            "OTIO_SCHEMA": "Stack.1",
            "name": "tracks",
            "children": [
                {"OTIO_SCHEMA": "Track.1", "name": "Video_Main", "kind": "Video", "children": video_children},
                {"OTIO_SCHEMA": "Track.1", "name": "Audio_Narration", "kind": "Audio", "children": audio_children},
            ],
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(otio_doc, indent=2), encoding="utf-8")
    return output_path
