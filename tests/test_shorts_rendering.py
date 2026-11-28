"""Shorts candidate and subtitle-window tests (no network or FFmpeg required)."""
from __future__ import annotations

from pathlib import Path

from upsc_studio.db.schemas import SceneSpec
from upsc_studio.video import shorts as shorts_module
from upsc_studio.video.shorts import ShortsRenderer


def _scene(scene_id: str, duration: float, claims: list[str]) -> SceneSpec:
    return SceneSpec(
        scene_id=scene_id,
        section_id=f"SEC_{scene_id[-2:]}",
        section_title=f"Section {scene_id}",
        learning_objective="Explain a source-backed point",
        narration_text="Source-backed narration.",
        claim_ids=claims,
        estimated_duration_sec=duration,
        visual_category="Concept graphic",
        primary_asset="unused.png",
        on_screen_title="A sourced concept",
        source_citations=["Source A"],
    )


def test_short_candidates_only_include_claim_linked_scenes_and_respect_58_seconds() -> None:
    scenes = [
        _scene("SCN_01", 8, []),
        _scene("SCN_02", 12, ["clm_1"]),
        _scene("SCN_03", 14, ["clm_2"]),
        _scene("SCN_04", 20, ["clm_3"]),
        _scene("SCN_05", 30, ["clm_4"]),
        _scene("SCN_06", 12, ["clm_5"]),
    ]
    candidates = ShortsRenderer.build_candidates(scenes, "Test chapter")
    assert candidates
    assert all(item["duration_sec"] <= 58 for item in candidates)
    assert all(item["claim_ids"] for item in candidates)
    assert all(item["independently_understandable"] is False for item in candidates)
    assert all("SCN_01" not in item["scene_ids"] for item in candidates)


def test_srt_slice_retimes_only_overlapping_subtitle_cues(tmp_path: Path) -> None:
    source = tmp_path / "source.srt"
    output = tmp_path / "short.srt"
    source.write_text(
        "1\n00:00:00,000 --> 00:00:04,000\nOpening\n\n"
        "2\n00:00:04,000 --> 00:00:09,000\nMain point\n\n"
        "3\n00:00:09,000 --> 00:00:13,000\nClosing\n",
        encoding="utf-8",
    )
    ShortsRenderer.slice_srt(source, 3.0, 7.0, output)
    rendered = output.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:01,000" in rendered
    assert "00:00:01,000 --> 00:00:06,000" in rendered
    assert "00:00:06,000 --> 00:00:07,000" in rendered
    assert "Opening" in rendered
    assert "Main point" in rendered
    assert "Closing" in rendered


def test_shorts_renderer_creates_vertical_manifest_and_sidecar_srt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(shorts_module, "find_ffmpeg", lambda: "ffmpeg-test")
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        Path(command[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(command[-1]).write_bytes(b"fake-ffmpeg-output")

    monkeypatch.setattr(shorts_module.subprocess, "run", fake_run)
    project = tmp_path / "project"
    renderer = ShortsRenderer(project)
    renderer.scene_dir.mkdir(parents=True, exist_ok=True)
    scene = SceneSpec(
        scene_id="SCN_01",
        section_id="SEC_01",
        section_title="A sourced principle",
        learning_objective="Explain the evidence",
        narration_text="A source-backed point.",
        claim_ids=["clm_1"],
        estimated_duration_sec=18.0,
        visual_category="Diagram",
        primary_asset="unused.png",
        on_screen_title="The principle",
    )
    (renderer.scene_dir / "SCN_01.mp4").write_bytes(b"fake-scene")
    narration = project / "audio.wav"
    narration.parent.mkdir(parents=True, exist_ok=True)
    narration.write_bytes(b"fake-audio")
    subtitles = project / "subtitles.srt"
    subtitles.parent.mkdir(parents=True, exist_ok=True)
    subtitles.write_text(
        "1\n00:00:00,000 --> 00:00:18,000\nA source-backed point.\n",
        encoding="utf-8",
    )
    candidates = ShortsRenderer.build_candidates([scene], "Chapter")
    result = renderer.render(
        "project-1", candidates, [scene], narration, subtitles,
    )
    assert result["rendered_count"] == 1
    assert result["shorts"][0]["resolution"] == "1080x1920"
    assert Path(result["shorts"][0]["video_path"]).is_file()
    assert Path(result["shorts"][0]["subtitles_path"]).is_file()
    assert len(commands) == 4
