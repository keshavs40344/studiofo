"""End-to-end automated UPSC chapter production orchestrator."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from upsc_studio.academic.pyq_engine import PYQEngine
from upsc_studio.academic.specialists import SpecialistProfileEngine
from upsc_studio.audio.processor import VoiceAudioProcessor
from upsc_studio.core.hardware import detect_hardware
from upsc_studio.core.logging_config import get_logger
from upsc_studio.db.schemas import ProjectStatus
from upsc_studio.graphics.generator import GraphicsGenerator
from upsc_studio.graphics.publishing import PublishingPackageBuilder
from upsc_studio.graphics.rights import AssetRightsLedger
from upsc_studio.graphics.visual_systems import ExtendedVisualSystems
from upsc_studio.ingestion.ingestor import DocumentIngestor
from upsc_studio.integrations.manim_worker import AnimationEngine
from upsc_studio.integrations.qgis_map import MapVisualEngine
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.qa.auditor import QAAuditor
from upsc_studio.qa.ten_gates import TenGateAuditor
from upsc_studio.research.verifier import EvidenceEngine
from upsc_studio.storyboard.director import StoryboardDirector
from upsc_studio.syllabus.engine import SyllabusEngine
from upsc_studio.teaching.duration_planner import DurationPlanner
from upsc_studio.teaching.engine import TeachingEngine
from upsc_studio.teaching.hinglish_director import HinglishDirector
from upsc_studio.qa.documentary_quality_gate import DocumentaryQualityGate
from upsc_studio.tts.adapter import PiperTTSEngine
from upsc_studio.video.renderer import VideoRenderer


class ChapterPipeline:
    """Orchestrates all production phases with WAITING_FOR_VOICE pause support."""

    def __init__(self, conn: sqlite3.Connection, projects_root: Path) -> None:
        self.conn = conn
        self.projects_root = projects_root
        self.project_mgr = ProjectManager(conn, projects_root)
        self.syllabus_engine = SyllabusEngine(conn)

    def run_pipeline(
        self,
        project_id: str,
        notes_files: list[Path] | None = None,
        typed_notes: str = "",
        voice_path: Optional[Path] = None,
        ai_narration: bool = False,
    ) -> dict:
        """Execute all automated stages for a chapter project."""
        project = self.project_mgr.get_project(project_id)
        project_dir = Path(project.root_dir)
        logger = get_logger(f"upsc_studio.{project_id}", project_dir / "logs" / "pipeline.log")

        self.project_mgr.update_status(project_id, ProjectStatus.PROCESSING)
        logger.info("Starting production pipeline for '%s'", project.chapter_title)

        # 1. Ingestion
        ingestor = DocumentIngestor(self.conn, project_dir)
        ingested_docs = []
        combined_text_parts: list[str] = []
        for fpath in notes_files or []:
            res = ingestor.ingest_file(project_id, fpath)
            ingested_docs.append(res.to_dict())
            combined_text_parts.extend(p.text for p in res.pages if p.text)
        if typed_notes.strip():
            res = ingestor.ingest_text(project_id, "user_typed_notes", typed_notes)
            ingested_docs.append(res.to_dict())
            combined_text_parts.append(typed_notes)
        combined_notes = "\n\n".join(combined_text_parts)

        # 2. Syllabus Mapping & Coverage Matrix
        chapter_map = self.syllabus_engine.map_chapter(
            project_id=project_id,
            project_dir=project_dir,
            chapter_title=project.chapter_title,
            notes_text=combined_notes,
        )

        # 3. Evidence & Claims Extraction
        evidence_engine = EvidenceEngine(self.conn, project_dir)
        if combined_notes.strip():
            notes_src_id = evidence_engine.add_source(
                project_id=project_id,
                title=f"User Notes for {project.chapter_title}",
                publisher="Project User",
                source_tier="USER_NOTES",
            )
            evidence_engine.extract_claims_from_text(
                project_id=project_id,
                chapter_section="User Supplied Notes",
                text=combined_notes,
                default_source_id=notes_src_id,
            )
        evidence_ledger = evidence_engine.export_ledger(project_id, project.cutoff_date)

        # 4. Specialist Profile, PYQs, Teaching Script & Duration Schedule
        specialist_key, specialist_profile = SpecialistProfileEngine().select_profile(
            project.chapter_title, chapter_map.get("primary_papers", [])
        )
        matched_pyqs = PYQEngine().match_chapter(project.chapter_title)

        teaching_engine = TeachingEngine(self.conn, project_dir)
        teaching_summary = teaching_engine.generate_teaching_package(
            project_id=project_id,
            chapter_title=project.chapter_title,
            chapter_map=chapter_map,
            notes_excerpt=combined_notes,
            tts_enabled=project.tts_enabled,
            target_duration_min=project.target_duration_min,
        )
        duration_schedule = DurationPlanner(teaching_engine.WORDS_PER_MINUTE).build_schedule(
            project_dir=project_dir,
            sections=teaching_summary["sections"],
            target_duration_min=project.target_duration_min,
        )

        # 4B. Hinglish Multi-Track Director (Display, Spoken TTS, and Subtitle synchronised tracks)
        hinglish_director = HinglishDirector(project_dir)
        hinglish_pkg = hinglish_director.export_documentary_package(
            chapter_title=project.chapter_title,
            project_dir=project_dir,
            target_duration_min=project.target_duration_min,
            verified_claims=evidence_ledger.get("claims", []),
        )

        # 5. Storyboard, Multi-Modal Documentary Visuals & Publishing Package
        director = StoryboardDirector(project_dir)
        scenes = director.build_storyboard(project.chapter_title, teaching_summary["sections"])
        rights_ledger = AssetRightsLedger(self.conn, project_dir)
        gfx = GraphicsGenerator(project_dir, rights_ledger)
        anim_engine = AnimationEngine(project_dir, rights_ledger)
        map_engine = MapVisualEngine(project_dir, rights_ledger)
        vis_engine = ExtendedVisualSystems(project_dir, rights_ledger)

        for scene in scenes:
            if scene.scene_id == "SCN_02":
                img_path = map_engine.render_institutional_map(
                    project_id,
                    scene.scene_id,
                    f"{project.chapter_title}: Institutional Scope",
                    [
                        ("Constitutional Basis", "Articles / Schedules"),
                        ("Implementing Authority", "Union & State Institutions"),
                        ("Judicial Oversight", "Supreme Court & High Courts"),
                    ],
                    source_label="Constitution of India",
                    ref_date=project.cutoff_date,
                )
                scene.primary_asset = str(img_path)
            elif scene.scene_id == "SCN_03":
                anim_res = anim_engine.render_process_animation(
                    project_id,
                    scene.scene_id,
                    f"{project.chapter_title}: Mechanism",
                    scene.on_screen_bullets or ["Trigger", "Institutional Review", "Outcome"],
                    source_citation=", ".join(scene.source_citations),
                    duration_sec=min(6.0, scene.estimated_duration_sec),
                )
                scene.primary_asset = anim_res["output_mp4"]
            elif scene.scene_id == "SCN_04":
                img_path = vis_engine.render_split_comparison(
                    project_id,
                    scene.scene_id,
                    f"{project.chapter_title}: Dimensions & Reforms",
                    "Strengths & Constitutional Mandate",
                    ["Protects democratic accountability", "Backed by judicial review"],
                    "Challenges & Way Forward",
                    ["Implementation delays", "Need for institutional clarity"],
                    source_label=", ".join(scene.source_citations),
                )
                scene.primary_asset = str(img_path)
            else:
                img_path = gfx.generate_scene_graphic(project_id, project.chapter_title, scene)
                scene.primary_asset = str(img_path)

        pub_pkg = PublishingPackageBuilder(project_dir, rights_ledger).build_package(
            project_id=project_id,
            chapter_title=project.chapter_title,
            primary_papers=chapter_map.get("primary_papers", []),
            scenes=scenes,
            specialist_key=specialist_key,
            specialist_profile=specialist_profile,
        )

        # Save updated storyboard with linked primary_asset paths
        import json

        (project_dir / "storyboard" / "storyboard.json").write_text(
            json.dumps([s.model_dump() for s in scenes], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # 6. Voice Selection: User Own Voice vs Built-in Licensed AI Narration vs WAITING_FOR_VOICE
        if voice_path is None and not ai_narration:
            self.project_mgr.update_status(project_id, ProjectStatus.WAITING_FOR_VOICE)
            auditor = QAAuditor(self.conn, project_dir)
            qa_report = auditor.run_all_checks(project_id)
            ten_gates = TenGateAuditor(self.conn, project_dir).run_ten_gates(project_id, scenes, None)
            logger.info("Voice absent: paused in WAITING_FOR_VOICE.")
            return {
                "project_id": project_id,
                "status": ProjectStatus.WAITING_FOR_VOICE.value,
                "specialist_profile": specialist_key,
                "matched_pyqs": len(matched_pyqs),
                "duration_schedule": duration_schedule,
                "publishing_package": pub_pkg,
                "recording_script": str(project_dir / "teaching" / "recording_script.md"),
                "chapter_map": chapter_map,
                "evidence_summary": evidence_ledger["status_counts"],
                "scenes_count": len(scenes),
                "qa": qa_report,
                "ten_gates": ten_gates,
            }

        # 7. Voice Processing (User Own Voice OR Piper AI Narration), Subtitles & FFmpeg Video Rendering
        if voice_path is not None:
            audio_proc = VoiceAudioProcessor(project_dir, rights_ledger=rights_ledger)
            audio_report = audio_proc.ingest_and_process(project_id, voice_path)
            srt_path = audio_proc.generate_subtitles(scenes, total_audio_sec=audio_report["duration_sec"])
            narration_wav = Path(audio_report["processed_file"])
        else:
            tts = PiperTTSEngine(project_dir, rights_ledger=rights_ledger)
            audio_report = tts.synthesize_scenes(project_id, scenes)
            srt_path = Path(audio_report["narration_transcript_srt"])
            narration_wav = Path(audio_report["narration_full_wav"])

        hw = detect_hardware(project_dir)
        renderer = VideoRenderer(self.conn, project_dir)
        render_manifest = renderer.render_project(
            project_id=project_id,
            scenes=scenes,
            narration_wav=narration_wav,
            subtitles_srt=srt_path,
            preset=hw.recommended_preset,
            fps=hw.recommended_fps,
            resolution=hw.recommended_resolution,
        )

        # 8. Final QA & 10-Gate Audit
        DurationPlanner(teaching_engine.WORDS_PER_MINUTE).build_schedule(
            project_dir=project_dir,
            sections=teaching_summary["sections"],
            target_duration_min=project.target_duration_min,
            actual_rendered_sec=audio_report.get("duration_sec"),
        )
        auditor = QAAuditor(self.conn, project_dir)
        qa_report = auditor.run_all_checks(project_id)
        ten_gates = TenGateAuditor(self.conn, project_dir).run_ten_gates(
            project_id, scenes, Path(render_manifest["final_video"])
        )
        doc_quality_report = DocumentaryQualityGate().evaluate_project(
            project_id=project_id,
            project_dir=project_dir,
            chapter_title=project.chapter_title,
            verified_claims_count=evidence_ledger["status_counts"].get("VERIFIED", 0),
            unverified_claims_count=sum(
                v for k, v in evidence_ledger["status_counts"].items() if k != "VERIFIED"
            ),
            rendered_video_path=Path(render_manifest["final_video"]),
            rendered_audio_path=narration_wav,
            subtitles_path=srt_path,
            script_sections_count=len(teaching_summary["sections"]),
            pyq_count=len(matched_pyqs),
        )
        final_status = (
            ProjectStatus.NEEDS_REVIEW
            if (
                qa_report["academic"]["status"] != "PASSED"
                or qa_report["media"]["status"] != "PASSED"
                or doc_quality_report.gate_status != "PASSED"
            )
            else ProjectStatus.APPROVED
        )
        self.project_mgr.update_status(project_id, final_status)
        logger.info("Pipeline finished with status %s", final_status.value)

        return {
            "project_id": project_id,
            "status": final_status.value,
            "specialist_profile": specialist_key,
            "matched_pyqs": len(matched_pyqs),
            "duration_schedule": duration_schedule,
            "publishing_package": pub_pkg,
            "ingested_docs": len(ingested_docs),
            "chapter_map": chapter_map,
            "evidence_summary": evidence_ledger["status_counts"],
            "scenes_count": len(scenes),
            "audio_report": audio_report,
            "render_manifest": render_manifest,
            "qa": qa_report,
            "ten_gates": ten_gates,
            "documentary_quality": doc_quality_report.to_dict(),
        }
