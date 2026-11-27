"""Persistent source/voice input bundle tests for resume and backup safety."""
from __future__ import annotations

from pathlib import Path

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate
from upsc_studio.pipeline.staged import StagedChapterPipeline
from upsc_studio.projects.manager import ProjectManager


def test_project_bundle_preserves_source_and_voice_for_later_resume(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "bundle.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(name="Input bundle", chapter_title="Economic planning")
    )
    root = Path(project.root_dir)
    original_doc = tmp_path / "source_notes.md"
    original_doc.write_text("# Economic planning\nOriginal source notes.", encoding="utf-8")
    original_voice = tmp_path / "creator.wav"
    original_voice.write_bytes(b"creator voice fixture")

    first_files, first_notes, first_voice = StagedChapterPipeline._resolve_input_bundle(
        root, [original_doc], "Additional typed notes.", None
    )
    assert first_notes == "Additional typed notes."
    assert first_voice is None
    assert len(first_files) == 1
    assert first_files[0].is_relative_to(root)
    assert first_files[0].read_text(encoding="utf-8") == original_doc.read_text(encoding="utf-8")

    second_files, second_notes, second_voice = StagedChapterPipeline._resolve_input_bundle(
        root, [], "", original_voice
    )
    assert second_files == first_files
    assert second_notes == first_notes
    assert second_voice is not None and second_voice.is_relative_to(root)
    assert second_voice.read_bytes() == original_voice.read_bytes()

    # A later rerun with no new source or voice upload reuses both saved inputs.
    third_files, third_notes, third_voice = StagedChapterPipeline._resolve_input_bundle(
        root, [], "", None
    )
    assert third_files == first_files
    assert third_notes == first_notes
    assert third_voice == second_voice


def test_input_manifest_rejects_missing_persisted_source_file(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "missing.db")
    project = ProjectManager(conn, tmp_path / "projects").create_project(
        ProjectCreate(name="Missing source", chapter_title="Public administration")
    )
    root = Path(project.root_dir)
    source = tmp_path / "source.txt"
    source.write_text("Source material.", encoding="utf-8")
    files, _, _ = StagedChapterPipeline._resolve_input_bundle(root, [source], "", None)
    files[0].unlink()

    try:
        StagedChapterPipeline._resolve_input_bundle(root, [], "", None)
    except FileNotFoundError as exc:
        assert "Previously saved project input is missing" in str(exc)
    else:
        raise AssertionError("A missing persisted project input must not be silently ignored.")
