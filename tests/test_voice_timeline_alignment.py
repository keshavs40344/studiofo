"""Voice-stage timeline is aligned to the measured audio duration."""
from __future__ import annotations

import json
from pathlib import Path

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, SceneSpec
from upsc_studio.pipeline.staged import StagedChapterPipeline
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.audio.processor import VoiceAudioProcessor


def _scene(scene_id: str, duration: float) -> SceneSpec:
    return SceneSpec(
        scene_id=scene_id,
        section_id=f"SEC_{scene_id[-2:]}",
        section_title=f"Section {scene_id}",
        learning_objective="Explain a source-backed point",
        narration_text="A source-backed narration sentence.",
        claim_ids=["clm_1"],
        estimated_duration_sec=duration,
        visual_category="Diagram",
        primary_asset="unused.png",
        on_screen_title="Source-backed point",
    )


def test_voice_stage_rescales_storyboard_to_actual_audio_duration(tmp_path: Path, monkeypatch) -> None:
    conn = init_db(tmp_path / "duration.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(name="Narration alignment", chapter_title="Federalism")
    )
    root = Path(project.root_dir)
    pipeline = StagedChapterPipeline(conn, tmp_path / "projects")
    paths = pipeline._paths(root)
    scenes = [_scene("SCN_01", 4.0), _scene("SCN_02", 6.0)]
    storyboard = root / "storyboard" / "storyboard.json"
    storyboard.parent.mkdir(parents=True, exist_ok=True)
    storyboard.write_text(
        json.dumps([scene.model_dump(mode="json") for scene in scenes]),
        encoding="utf-8",
    )
    voice_input = tmp_path / "voice.wav"
    voice_input.write_bytes(b"voice-input")
    processed = root / "audio" / "processed" / "clean.wav"
    processed.parent.mkdir(parents=True, exist_ok=True)
    processed.write_bytes(b"processed-audio")
    subtitles = root / "subtitles" / "subtitles.srt"
    subtitles.parent.mkdir(parents=True, exist_ok=True)
    subtitles.write_text("1\n00:00:00,000 --> 00:00:30,000\nNarration\n", encoding="utf-8")

    monkeypatch.setattr(
        VoiceAudioProcessor,
        "ingest_and_process",
        lambda self, project_id, voice_path: {
            "processed_file": str(processed),
            "duration_sec": 30.0,
            "mean_volume_db": -20.0,
            "max_volume_db": -2.0,
        },
    )
    monkeypatch.setattr(
        VoiceAudioProcessor,
        "generate_subtitles",
        lambda self, scenes, total_audio_sec=None, output_path=None: subtitles,
    )

    result = pipeline._stage_voice(
        project.id, root, paths, voice_input, ai_narration=False
    )
    saved_scenes = [
        SceneSpec.model_validate(item)
        for item in json.loads(storyboard.read_text(encoding="utf-8"))
    ]
    timeline_total = sum(scene.estimated_duration_sec for scene in saved_scenes)

    assert result["status"] == "COMPLETED"
    assert timeline_total == 30.0
    assert saved_scenes[0].estimated_duration_sec == 12.0
    assert saved_scenes[1].estimated_duration_sec == 18.0
    voice_report = json.loads(paths["voice"].read_text(encoding="utf-8"))
    assert voice_report["timeline_alignment"]["method"] == "SCENE_DURATION_SCALED_TO_ACTUAL_NARRATION"
