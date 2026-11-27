"""Regression tests proving a voice pause resumes from the first changed stage."""
from __future__ import annotations

import json
from pathlib import Path

from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, ProjectStatus
from upsc_studio.pipeline.staged import StagedChapterPipeline
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.research.verifier import EvidenceEngine


def test_staged_pipeline_reuses_upstream_artifacts_when_voice_arrives(
    tmp_path: Path, monkeypatch
) -> None:
    conn = init_db(tmp_path / "staged.db")
    projects_root = tmp_path / "projects"
    project = ProjectManager(conn, projects_root).create_project(
        ProjectCreate(name="Stage resume", chapter_title="Federalism in India")
    )
    pipeline = StagedChapterPipeline(conn, projects_root)
    calls = {name: 0 for name in ("ingestion", "academic", "teaching", "visuals", "voice", "render", "qa")}

    def write(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def ingestion(self, project_id, project_dir, paths, notes_files, typed_notes):
        calls["ingestion"] += 1
        paths["notes"].parent.mkdir(parents=True, exist_ok=True)
        paths["notes"].write_text(typed_notes, encoding="utf-8")
        write(paths["ingestion"], {"ingested_count": 1})
        return {"status": "COMPLETED", "artifact": str(paths["ingestion"])}

    def academic(self, project_id, project_dir, paths, project_obj):
        calls["academic"] += 1
        write(paths["academic"], {
            "chapter_map": {"primary_papers": ["Mains GS Paper II"]},
            "evidence_summary": {"VERIFIED": 0, "UNVERIFIED": 1},
        })
        return {"status": "COMPLETED", "artifact": str(paths["academic"])}

    def teaching(self, project_id, project_dir, paths, chapter_map):
        calls["teaching"] += 1
        write(paths["teaching"], {
            "teaching_summary": {"sections": [{"section_id": "SEC_01", "title": "Intro",
                "objective": "Explain federalism", "narration": "Federalism divides powers.",
                "duration_sec": 12, "visual_category": "Flowchart", "claim_ids": []}]},
            "specialist_key": "GS-II", "specialist_profile": {},
            "matched_pyqs": 0, "duration_schedule": {"status": "FITS_TARGET_DURATION"},
            "recording_script": str(project_dir / "teaching" / "recording_script.md"),
        })
        return {"status": "COMPLETED", "artifact": str(paths["teaching"])}

    def visuals(self, project_id, project_dir, paths, project_obj, chapter_map, teaching_obj):
        calls["visuals"] += 1
        write(paths["visuals"], {"publishing_package": {"video_title": "Federalism"},
                                 "scenes_count": 1, "storyboard_path": "storyboard.json"})
        return {"status": "COMPLETED", "artifact": str(paths["visuals"])}

    def voice(self, project_id, project_dir, paths, voice_path, ai_narration):
        calls["voice"] += 1
        if voice_path is None:
            report = {"pipeline_status": ProjectStatus.WAITING_FOR_VOICE.value,
                      "voice_wait_reason": "Test pause", "qa": {"rights": {"status": "PASSED"}},
                      "ten_gates": {"pending_gates": ["G_VOICE"]}}
            write(paths["voice"], report)
            return {"status": "BLOCKED", "pipeline_status": report["pipeline_status"],
                    "artifact": str(paths["voice"])}
        report = {"pipeline_status": "VOICE_READY", "audio_report": {"duration_sec": 12.0},
                  "narration_wav": str(voice_path), "subtitles_srt": str(voice_path)}
        write(paths["voice"], report)
        return {"status": "COMPLETED", "artifact": str(paths["voice"])}

    def render(self, project_id, project_dir, paths, teaching_obj, voice_obj):
        calls["render"] += 1
        report = {"render_manifest": {"final_video": str(project_dir / "video" / "final.mp4")},
                  "duration_schedule": {"status": "FITS_TARGET_DURATION"}}
        write(paths["render"], report)
        return {"status": "COMPLETED", "artifact": str(paths["render"])}

    def qa(self, project_id, project_dir, paths):
        calls["qa"] += 1
        report = {"pipeline_status": ProjectStatus.APPROVED.value,
                  "qa": {"academic": {"status": "PASSED"}, "rights": {"status": "PASSED"},
                         "media": {"status": "PASSED"}},
                  "ten_gates": {"failed_gates": [], "pending_gates": []}}
        write(paths["qa"], report)
        self.project_mgr.update_status(project_id, ProjectStatus.APPROVED)
        return {"status": "COMPLETED", "pipeline_status": ProjectStatus.APPROVED.value,
                "artifact": str(paths["qa"])}

    monkeypatch.setattr(StagedChapterPipeline, "_stage_ingestion", ingestion)
    monkeypatch.setattr(StagedChapterPipeline, "_stage_academic", academic)
    monkeypatch.setattr(StagedChapterPipeline, "_stage_teaching", teaching)
    monkeypatch.setattr(StagedChapterPipeline, "_stage_visuals", visuals)
    monkeypatch.setattr(StagedChapterPipeline, "_stage_voice", voice)
    monkeypatch.setattr(StagedChapterPipeline, "_stage_render", render)
    monkeypatch.setattr(StagedChapterPipeline, "_stage_qa", qa)

    first = pipeline.run_staged(project.id, typed_notes="Federalism distributes constitutional powers.")
    assert first["status"] == ProjectStatus.WAITING_FOR_VOICE.value
    assert first["pipeline_stages"]["task_count"] == 7
    assert first["pipeline_stages"]["blocked"] == 3
    assert calls == {"ingestion": 1, "academic": 1, "teaching": 1,
                     "visuals": 1, "voice": 1, "render": 0, "qa": 0}

    # An identical retry reuses the cached pause and does not redo completed stages.
    second = pipeline.run_staged(project.id, typed_notes="Federalism distributes constitutional powers.")
    assert second["status"] == ProjectStatus.WAITING_FOR_VOICE.value
    assert calls == {"ingestion": 1, "academic": 1, "teaching": 1,
                     "visuals": 1, "voice": 1, "render": 0, "qa": 0}

    recording = tmp_path / "creator_voice.wav"
    recording.write_bytes(b"test voice input")
    third = pipeline.run_staged(
        project.id, typed_notes="Federalism distributes constitutional powers.",
        voice_path=recording,
    )
    assert third["status"] == ProjectStatus.APPROVED.value
    assert calls == {"ingestion": 1, "academic": 1, "teaching": 1,
                     "visuals": 1, "voice": 2, "render": 1, "qa": 1}
    assert third["pipeline_stages"]["status"] == "COMPLETED"

    # A new manual-review decision reruns QA without rebuilding production artifacts.
    review_path = Path(project.root_dir) / "qa" / "manual_review.json"
    review_path.write_text(json.dumps({"reviewer": "Creator", "checks": {"teaching_clarity": True}}),
                           encoding="utf-8")
    fourth = pipeline.run_staged(
        project.id, typed_notes="Federalism distributes constitutional powers.",
        voice_path=recording,
    )
    assert fourth["status"] == ProjectStatus.APPROVED.value
    assert calls == {"ingestion": 1, "academic": 1, "teaching": 1,
                     "visuals": 1, "voice": 2, "render": 1, "qa": 2}

    # Newly registered external research invalidates academic and all dependent stages,
    # while ingestion remains unchanged.
    evidence = EvidenceEngine(conn, Path(project.root_dir))
    source_id = evidence.add_source(
        project.id, "External report", "Publisher", "OTHER",
        url="https://example.org/report",
    )
    evidence.add_claim(
        project.id, "A source-backed claim added after the first production pass.",
        "Research", source_id=source_id,
    )
    fifth = pipeline.run_staged(
        project.id, typed_notes="Federalism distributes constitutional powers.",
        voice_path=recording,
    )
    assert fifth["status"] == ProjectStatus.APPROVED.value
    assert calls == {"ingestion": 1, "academic": 2, "teaching": 2,
                     "visuals": 2, "voice": 3, "render": 2, "qa": 3}
