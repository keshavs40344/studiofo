"""Independently resumable documentary production stages backed by the SQLite task runtime.

Each stage writes its durable artifacts to the project workspace and exposes only
small metadata/path summaries to SQLite. Stage fingerprints allow completed upstream
work to be reused when a later input (for example, the creator's voice recording)
arrives. This is a local-first pipeline, not a claim of semantic fact verification.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from upsc_studio.academic.pyq_engine import PYQEngine
from upsc_studio.academic.specialists import SpecialistProfileEngine
from upsc_studio.agents.runtime import AgentTaskStore, DependencyScheduler, TaskSpec
from upsc_studio.audio.processor import VoiceAudioProcessor
from upsc_studio.core.hardware import detect_hardware
from upsc_studio.core.paths import sha256_file
from upsc_studio.db.schemas import ProjectStatus, SceneSpec
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
from upsc_studio.research.discovery import ResearchDiscovery
from upsc_studio.storyboard.director import StoryboardDirector
from upsc_studio.syllabus.engine import SyllabusEngine
from upsc_studio.teaching.duration_planner import DurationPlanner
from upsc_studio.teaching.engine import TeachingEngine
from upsc_studio.tts.adapter import PiperTTSEngine
from upsc_studio.video.renderer import VideoRenderer
from upsc_studio.video.shorts import ShortsRenderer


PIPELINE_STAGE_VERSION = "chapter-stages-v2"


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temp.replace(path)


def _read_json(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Required stage artifact is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _external_evidence_fingerprint(conn: sqlite3.Connection, project_id: str) -> str:
    """Fingerprint manually registered research; ignore pipeline-generated user-note records."""
    sources = [
        dict(row) for row in conn.execute(
            """
            SELECT id, title, publisher, url, pub_date, source_tier
            FROM sources
            WHERE project_id = ? AND source_tier <> 'USER_NOTES'
            ORDER BY id
            """,
            (project_id,),
        ).fetchall()
    ]
    claims = [
        dict(row) for row in conn.execute(
            """
            SELECT c.id, c.statement, c.chapter_section, c.source_id,
                   c.page_or_section, c.ref_period, c.status, c.verification_notes
            FROM claims AS c
            LEFT JOIN sources AS s ON s.id = c.source_id
            WHERE c.project_id = ?
              AND (c.source_id IS NULL OR s.source_tier <> 'USER_NOTES')
            ORDER BY c.id
            """,
            (project_id,),
        ).fetchall()
    ]
    return _fingerprint({"sources": sources, "claims": claims})


class StagedChapterPipeline:
    """Execute resumable ingestion, academic, teaching, visuals, voice, render and QA stages."""

    def __init__(self, conn: sqlite3.Connection, projects_root: Path) -> None:
        self.conn = conn
        self.projects_root = Path(projects_root)
        self.project_mgr = ProjectManager(conn, self.projects_root)

    @staticmethod
    def _resolve_input_bundle(
        project_dir: Path,
        notes_files: list[Path] | None,
        typed_notes: str,
        voice_path: Path | None = None,
    ) -> tuple[list[Path], str, Path | None]:
        """Persist lesson sources and creator voice for safe continuation/retry runs."""
        project_root = project_dir.resolve()
        root = project_root / "inputs" / "production_bundle"
        files_dir = root / "files"
        voice_dir = root / "voice"
        manifest_path = root / "input_manifest.json"
        has_new_notes = bool(notes_files) or bool(typed_notes.strip())
        has_new_voice = voice_path is not None
        manifest = _read_json(manifest_path) if manifest_path.is_file() else {
            "version": 1,
            "files": [],
            "typed_notes_path": None,
            "typed_notes_sha256": hashlib.sha256(b"").hexdigest(),
            "voice": None,
        }
        if manifest.get("version") != 1 or not isinstance(manifest.get("files"), list):
            raise ValueError("Saved production input manifest is invalid; inspect or replace project inputs.")

        if has_new_notes:
            files_dir.mkdir(parents=True, exist_ok=True)
            persisted: list[dict[str, Any]] = []
            for source_item in notes_files or []:
                source = Path(source_item).expanduser().resolve()
                if not source.is_file():
                    raise FileNotFoundError(f"Notes file not found: {source}")
                digest = sha256_file(source)
                suffix = source.suffix.lower()
                destination = files_dir / f"{digest}{suffix}"
                if source != destination.resolve() and (
                    not destination.is_file() or sha256_file(destination) != digest
                ):
                    temporary = destination.with_suffix(destination.suffix + ".tmp")
                    shutil.copy2(source, temporary)
                    temporary.replace(destination)
                persisted.append({
                    "path": destination.relative_to(project_root).as_posix(),
                    "sha256": digest,
                    "size": destination.stat().st_size,
                })

            typed_path: str | None = None
            if typed_notes.strip():
                typed_file = root / "typed_notes.txt"
                typed_file.parent.mkdir(parents=True, exist_ok=True)
                temporary = typed_file.with_suffix(".txt.tmp")
                temporary.write_text(typed_notes, encoding="utf-8")
                temporary.replace(typed_file)
                typed_path = typed_file.relative_to(project_root).as_posix()
            manifest["files"] = persisted
            manifest["typed_notes_path"] = typed_path
            manifest["typed_notes_sha256"] = hashlib.sha256(
                typed_notes.encode("utf-8")
            ).hexdigest()

        if has_new_voice:
            source_voice = Path(voice_path).expanduser().resolve()
            if not source_voice.is_file():
                raise FileNotFoundError(f"Voice recording not found: {source_voice}")
            voice_dir.mkdir(parents=True, exist_ok=True)
            voice_digest = sha256_file(source_voice)
            voice_destination = voice_dir / f"{voice_digest}{source_voice.suffix.lower()}"
            if source_voice != voice_destination.resolve() and (
                not voice_destination.is_file() or sha256_file(voice_destination) != voice_digest
            ):
                temporary = voice_destination.with_suffix(
                    voice_destination.suffix + ".tmp"
                )
                shutil.copy2(source_voice, temporary)
                temporary.replace(voice_destination)
            manifest["voice"] = {
                "path": voice_destination.relative_to(project_root).as_posix(),
                "sha256": voice_digest,
                "size": voice_destination.stat().st_size,
            }

        if has_new_notes or has_new_voice or not manifest_path.is_file():
            _write_json(manifest_path, manifest)

        resolved_files: list[Path] = []
        for item in manifest["files"]:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise ValueError("Saved input manifest contains an invalid file reference.")
            candidate = (project_root / item["path"]).resolve()
            try:
                candidate.relative_to(project_root)
            except ValueError as exc:
                raise ValueError("Saved input path escapes the project workspace.") from exc
            if not candidate.is_file():
                raise FileNotFoundError(
                    f"Previously saved project input is missing: {candidate.name}. Re-upload the source file."
                )
            if item.get("sha256") and sha256_file(candidate) != item["sha256"]:
                raise ValueError(
                    f"Previously saved project input changed unexpectedly: {candidate.name}. Re-upload it."
                )
            resolved_files.append(candidate)

        resolved_notes = ""
        typed_relative = manifest.get("typed_notes_path")
        if typed_relative:
            typed_file = (project_root / str(typed_relative)).resolve()
            try:
                typed_file.relative_to(project_root)
            except ValueError as exc:
                raise ValueError("Saved typed-notes path escapes the project workspace.") from exc
            if not typed_file.is_file():
                raise FileNotFoundError("Previously saved typed notes are missing; re-enter the notes.")
            resolved_notes = typed_file.read_text(encoding="utf-8")
            expected_hash = manifest.get("typed_notes_sha256")
            if expected_hash and hashlib.sha256(resolved_notes.encode("utf-8")).hexdigest() != expected_hash:
                raise ValueError("Saved typed notes changed unexpectedly; re-enter the notes.")

        resolved_voice: Path | None = None
        voice_record = manifest.get("voice")
        if voice_record:
            if not isinstance(voice_record, dict) or not isinstance(voice_record.get("path"), str):
                raise ValueError("Saved creator voice reference is invalid.")
            candidate_voice = (project_root / voice_record["path"]).resolve()
            try:
                candidate_voice.relative_to(project_root)
            except ValueError as exc:
                raise ValueError("Saved voice path escapes the project workspace.") from exc
            if not candidate_voice.is_file():
                raise FileNotFoundError("Previously saved creator voice is missing; upload the recording again.")
            if voice_record.get("sha256") and sha256_file(candidate_voice) != voice_record["sha256"]:
                raise ValueError("Saved creator voice changed unexpectedly; upload the recording again.")
            resolved_voice = candidate_voice

        return resolved_files, resolved_notes, resolved_voice

    @staticmethod
    def _file_fingerprint(paths: list[Path] | None, typed_notes: str) -> tuple[str, list[dict[str, Any]]]:
        refs: list[dict[str, Any]] = []
        for item in paths or []:
            path = Path(item).expanduser().resolve()
            if not path.is_file():
                raise FileNotFoundError(f"Notes file not found: {path}")
            refs.append({"name": path.name, "size": path.stat().st_size, "sha256": sha256_file(path)})
        typed_hash = hashlib.sha256(typed_notes.encode("utf-8")).hexdigest()
        return _fingerprint({"files": refs, "typed_notes_sha256": typed_hash}), refs

    @staticmethod
    def _scene_specs(project_dir: Path) -> list[SceneSpec]:
        raw = _read_json(project_dir / "storyboard" / "storyboard.json")
        return [SceneSpec.model_validate(item) for item in raw]

    def _paths(self, project_dir: Path) -> dict[str, Path]:
        root = project_dir / "workflow" / "stages"
        root.mkdir(parents=True, exist_ok=True)
        return {
            "ingestion": root / "ingestion.json",
            "notes": root / "combined_notes.txt",
            "academic": root / "academic.json",
            "teaching": root / "teaching.json",
            "visuals": root / "visuals.json",
            "voice": root / "voice.json",
            "render": root / "render.json",
            "qa": root / "qa.json",
        }

    def _stage_ingestion(
        self, project_id: str, project_dir: Path, paths: dict[str, Path],
        notes_files: list[Path], typed_notes: str,
    ) -> dict[str, Any]:
        ingestor = DocumentIngestor(self.conn, project_dir)
        ingested_docs: list[dict[str, Any]] = []
        text_parts: list[str] = []
        for path in notes_files:
            result = ingestor.ingest_file(project_id, path)
            ingested_docs.append(result.to_dict())
            text_parts.extend(page.text for page in result.pages if page.text)
        if typed_notes.strip():
            result = ingestor.ingest_text(project_id, "user_typed_notes", typed_notes)
            ingested_docs.append(result.to_dict())
            text_parts.append(typed_notes)
        combined = "\n\n".join(text_parts)
        paths["notes"].parent.mkdir(parents=True, exist_ok=True)
        temp = paths["notes"].with_suffix(".txt.tmp")
        temp.write_text(combined, encoding="utf-8")
        temp.replace(paths["notes"])
        report = {"ingested_docs": ingested_docs, "ingested_count": len(ingested_docs),
                  "combined_notes_path": str(paths["notes"])}
        _write_json(paths["ingestion"], report)
        return {"status": "COMPLETED", "artifact": str(paths["ingestion"]),
                "ingested_count": len(ingested_docs), "notes_path": str(paths["notes"])}

    def _stage_academic(self, project_id: str, project_dir: Path, paths: dict[str, Path],
                        project: Any) -> dict[str, Any]:
        notes = paths["notes"].read_text(encoding="utf-8") if paths["notes"].is_file() else ""
        if project.content_category == "upsc":
            chapter_map = SyllabusEngine(self.conn).map_chapter(
                project_id=project_id, project_dir=project_dir,
                chapter_title=project.chapter_title, notes_text=notes,
            )
            category_map_path = project_dir / "research" / "topic_map.json"
            category_map_path.unlink(missing_ok=True)
        else:
            # Non-UPSC categories use a topic map, not a fabricated UPSC syllabus match.
            headings = [
                line.lstrip("#").strip()
                for line in notes.splitlines()
                if line.lstrip().startswith("#") and line.lstrip("#").strip()
            ]
            claim_sections = [
                row["chapter_section"] for row in self.conn.execute(
                    "SELECT DISTINCT chapter_section FROM claims WHERE project_id = ? ORDER BY chapter_section",
                    (project_id,),
                ).fetchall()
            ]
            topic_names = list(dict.fromkeys([project.chapter_title, *headings, *claim_sections]))
            topic_map = {
                "project_id": project_id,
                "content_category": project.content_category,
                "topic_title": project.chapter_title,
                "topics": [
                    {"title": title, "coverage_status": "REVIEW_REQUIRED",
                     "basis": "project_title_or_supplied_material_heading"}
                    for title in topic_names
                ],
                "coverage_status": "REVIEW_REQUIRED",
                "scope_review_required": True,
                "research_cutoff_date": (
                    project.cutoff_date if project.content_category == "current_affairs" else None
                ),
            }
            category_map_path = project_dir / "research" / "topic_map.json"
            _write_json(category_map_path, topic_map)
            chapter_map = {
                "project_id": project_id,
                "chapter_title": project.chapter_title,
                "content_category": project.content_category,
                "primary_papers": [],
                "topic_dimensions": topic_map["topics"],
                "topic_map_path": str(category_map_path),
                "scope_review_required": True,
                "research_cutoff_date": topic_map["research_cutoff_date"],
            }
        evidence = EvidenceEngine(self.conn, project_dir)
        note_source_title = f"User Notes for {project.chapter_title}"
        note_sources = self.conn.execute(
            """
            SELECT id, notes FROM sources
            WHERE project_id = ? AND title = ? AND publisher = 'Project User'
              AND source_tier = 'USER_NOTES'
            ORDER BY access_date, id
            """,
            (project_id, note_source_title),
        ).fetchall()
        note_digest = hashlib.sha256(notes.encode("utf-8")).hexdigest()
        if not notes.strip():
            for old_source in note_sources:
                self.conn.execute("DELETE FROM claims WHERE source_id = ?", (old_source["id"],))
                self.conn.execute("DELETE FROM sources WHERE id = ?", (old_source["id"],))
            self.conn.commit()
        else:
            if note_sources:
                source_id = note_sources[0]["id"]
                if note_sources[0]["notes"] != note_digest:
                    self.conn.execute("DELETE FROM claims WHERE source_id = ?", (source_id,))
                    self.conn.execute(
                        "UPDATE sources SET notes = ? WHERE id = ?", (note_digest, source_id)
                    )
                    self.conn.commit()
                for duplicate in note_sources[1:]:
                    self.conn.execute("DELETE FROM claims WHERE source_id = ?", (duplicate["id"],))
                    self.conn.execute("DELETE FROM sources WHERE id = ?", (duplicate["id"],))
                self.conn.commit()
            else:
                source_id = evidence.add_source(
                    project_id=project_id,
                    title=note_source_title,
                    publisher="Project User",
                    source_tier="USER_NOTES",
                    notes=note_digest,
                )
            evidence.extract_claims_from_text(
                project_id=project_id,
                chapter_section="User Supplied Notes",
                text=notes,
                default_source_id=source_id,
            )
        discovery_report: dict[str, Any] = {
            "status": "AUTO_RESEARCH_DISABLED",
            "registered_count": 0,
            "fact_checking": "NOT_PERFORMED",
        }
        if os.getenv("UPSC_STUDIO_AUTO_RESEARCH", "1").strip().lower() not in {"0", "false", "no"}:
            category_query = {
                "upsc": "UPSC India constitutional law official report research",
                "general_knowledge": "India general knowledge authoritative reference",
                "current_affairs": "India current affairs policy report",
                "deep_dive": "India research academic study",
            }.get(project.content_category, "India research")
            try:
                discovery_report = ResearchDiscovery(evidence).discover(
                    project_id=project_id,
                    query=f"{project.chapter_title} {category_query}",
                    limit=5,
                    cutoff_date=project.cutoff_date if project.content_category == "current_affairs" else None,
                    require_dated_sources=project.content_category == "current_affairs",
                )
            except Exception as exc:
                discovery_report = {
                    "status": "DISCOVERY_ERROR",
                    "registered_count": 0,
                    "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                    "fact_checking": "NOT_PERFORMED",
                }
        ledger = evidence.export_ledger(project_id, project.cutoff_date)
        report = {
            "chapter_map": chapter_map,
            "evidence_summary": ledger["status_counts"],
            "research_discovery": discovery_report,
        }
        _write_json(paths["academic"], report)
        return {
            "status": "COMPLETED",
            "artifact": str(paths["academic"]),
            "evidence_summary": ledger["status_counts"],
            "research_candidates": discovery_report.get("registered_count", 0),
            "research_discovery_status": discovery_report.get("status"),
        }

    def _stage_teaching(self, project_id: str, project_dir: Path, paths: dict[str, Path],
                        chapter_map: dict[str, Any]) -> dict[str, Any]:
        project = self.project_mgr.get_project(project_id)
        if project.content_category == "upsc":
            specialist_key, specialist_profile = SpecialistProfileEngine().select_profile(
                project.chapter_title, chapter_map.get("primary_papers", []),
            )
            matched_pyqs = PYQEngine().match_chapter(project.chapter_title)
        else:
            from upsc_studio.universal.domain_engine import UniversalKnowledgeEngine
            notes = paths["notes"].read_text(encoding="utf-8") if paths["notes"].is_file() else ""
            specialist_key, specialist_profile = UniversalKnowledgeEngine().select_domain_profile(
                project.chapter_title, project.content_category, notes
            )
            matched_pyqs = []
        engine = TeachingEngine(self.conn, project_dir)
        notes = paths["notes"].read_text(encoding="utf-8") if paths["notes"].is_file() else ""
        teaching_summary = engine.generate_teaching_package(
            project_id=project_id, chapter_title=project.chapter_title, chapter_map=chapter_map,
            notes_excerpt=notes, tts_enabled=project.tts_enabled,
            target_duration_min=project.target_duration_min,
            content_category=project.content_category,
        )
        duration = DurationPlanner(engine.WORDS_PER_MINUTE).build_schedule(
            project_dir=project_dir, sections=teaching_summary["sections"],
            target_duration_min=project.target_duration_min,
        )
        report = {
            "teaching_summary": teaching_summary,
            "specialist_key": specialist_key,
            "specialist_profile": specialist_profile,
            "matched_pyqs": len(matched_pyqs),
            "duration_schedule": duration,
            "recording_script": str(project_dir / "teaching" / "recording_script.md"),
        }
        _write_json(paths["teaching"], report)
        return {"status": "COMPLETED", "artifact": str(paths["teaching"]),
                "specialist_profile": specialist_key, "matched_pyqs": len(matched_pyqs),
                "recording_script": report["recording_script"]}

    def _stage_visuals(self, project_id: str, project_dir: Path, paths: dict[str, Path],
                       project: Any, chapter_map: dict[str, Any],
                       teaching: dict[str, Any]) -> dict[str, Any]:
        sections = teaching["teaching_summary"]["sections"]
        specialist_key = teaching["specialist_key"]
        specialist_profile = teaching["specialist_profile"]
        scenes = StoryboardDirector(project_dir).build_storyboard(project.chapter_title, sections)
        rights = AssetRightsLedger(self.conn, project_dir)
        graphics = GraphicsGenerator(project_dir, rights)
        animations = AnimationEngine(project_dir, rights)
        maps = MapVisualEngine(project_dir, rights)
        visuals = ExtendedVisualSystems(project_dir, rights)

        from upsc_studio.graphics.documentary_animations import DocumentaryAnimationSuite
        from upsc_studio.graphics.geojson_renderer import GeoJSONMapRenderer
        doc_anim = DocumentaryAnimationSuite(project_dir, rights)
        geojson_maps = GeoJSONMapRenderer(project_dir, rights)

        specialised_visual_types = {
            "HISTORICAL_TIMELINE", "GEOGRAPHICAL_MAP", "SPLIT_COMPARISON",
            "BEFORE_AFTER", "CAUSE_AND_EFFECT", "INSTITUTIONAL_DIAGRAM",
            "FLOWCHART", "STEP_BY_STEP_MECHANISM", "SCIENTIFIC_ILLUSTRATION",
            "DATA_VISUALISATION", "STATISTICAL_COMPARISON",
        }
        for idx, scene in enumerate(scenes):
            vtype = str((scene.metadata or {}).get("visual_type") or "").upper()
            bullets = scene.on_screen_bullets or [scene.learning_objective or project.chapter_title]
            # Resolve scene citations to actual external source titles and pinpoint references.
            # Internal claim IDs are never rendered as if they were source citations.
            citations: list[str] = []
            citation_records: list[dict[str, str | None]] = []
            for claim_id in scene.claim_ids:
                source_row = self.conn.execute(
                    """
                    SELECT c.status, c.page_or_section, s.title, s.publisher, s.url, s.source_tier
                    FROM claims AS c
                    JOIN sources AS s ON s.id = c.source_id
                    WHERE c.project_id = ? AND c.id = ?
                    """,
                    (project_id, claim_id),
                ).fetchone()
                if (
                    source_row
                    and source_row["status"] == "VERIFIED"
                    and source_row["source_tier"] != "USER_NOTES"
                    and source_row["url"]
                    and str(source_row["url"]).strip()
                ):
                    citation_text = str(source_row["title"]).strip()
                    if source_row["publisher"]:
                        citation_text += f" — {str(source_row['publisher']).strip()}"
                    if source_row["page_or_section"]:
                        citation_text += f" — {str(source_row['page_or_section']).strip()}"
                    if citation_text not in citations:
                        citations.append(citation_text)
                    citation_records.append(
                        {
                            "claim_id": claim_id,
                            "title": str(source_row["title"] or "").strip(),
                            "publisher": str(source_row["publisher"] or "").strip(),
                            "url": str(source_row["url"] or "").strip(),
                            "page_or_section": (
                                str(source_row["page_or_section"]).strip()
                                if source_row["page_or_section"] else None
                            ),
                            "source_tier": str(source_row["source_tier"] or "").strip(),
                        }
                    )
            scene.metadata["citation_records"] = citation_records
            scene.source_citations = citations
            scene.metadata["citation_status"] = (
                "VERIFIED_EXTERNAL_SOURCE_LINKED" if citations else "SOURCE_REVIEW_REQUIRED"
            )
            citation = "; ".join(citations[:3]) if citations else "Source attribution pending review"
            clip_dur = min(10.0, max(5.0, float(scene.estimated_duration_sec)))

            if idx == 0 and vtype not in specialised_visual_types:
                asset = graphics.generate_scene_graphic(project_id, project.chapter_title, scene)
                scene.metadata["rendered_visual_kind"] = "TITLE_OR_CONCEPT_GRAPHIC"
                scene.primary_asset = str(asset)
            elif vtype == "HISTORICAL_TIMELINE":
                raw_events = (scene.metadata or {}).get("timeline_events")
                events = (
                    [
                        (str(item["date"]).strip(), str(item["label"]).strip())
                        for item in raw_events
                        if isinstance(item, dict)
                        and str(item.get("date", "")).strip()
                        and str(item.get("label", "")).strip()
                    ][:8]
                    if isinstance(raw_events, list) else []
                )
                if len(events) >= 2 and scene.source_citations:
                    asset = doc_anim.render_timeline_progression(
                        project_id, scene.scene_id, scene.section_title, events, citation, duration_sec=clip_dur
                    )
                    scene.metadata["rendered_visual_kind"] = "TIMELINE"
                else:
                    asset = doc_anim.render_process_demonstration(
                        project_id, scene.scene_id, scene.section_title, bullets[:4],
                        citation, duration_sec=clip_dur
                    )
                    scene.metadata["rendered_visual_kind"] = "PROCESS_FALLBACK_NOT_TIMELINE"
                    scene.metadata["visual_data_warning"] = (
                        "Timeline requested but not rendered: at least two sourced dated events are required. "
                        "This fallback is a draft only and blocks publication."
                    )
                scene.primary_asset = str(asset)
            elif vtype == "GEOGRAPHICAL_MAP":
                raw_geojson = (scene.metadata or {}).get("map_geojson")
                geojson_data: dict[str, Any] | None = None
                map_input_error: str | None = None
                if isinstance(raw_geojson, dict):
                    geojson_data = raw_geojson
                elif isinstance(raw_geojson, str) and raw_geojson.strip():
                    supplied_path = Path(raw_geojson).expanduser().resolve()
                    try:
                        supplied_path.relative_to(project_dir.resolve())
                        if not supplied_path.is_file():
                            map_input_error = "The supplied GeoJSON file does not exist in the project workspace."
                        else:
                            geojson_data = json.loads(supplied_path.read_text(encoding="utf-8"))
                    except ValueError as exc:
                        map_input_error = str(exc)
                    except (OSError, json.JSONDecodeError) as exc:
                        map_input_error = f"GeoJSON could not be loaded: {type(exc).__name__}"

                citation_record = citation_records[0] if citation_records else {}
                source_url = str(citation_record.get("url") or "").strip()
                map_failure: str | None = map_input_error
                if geojson_data and scene.source_citations and source_url:
                    try:
                        asset = geojson_maps.render(
                            project_id=project_id,
                            scene_id=scene.scene_id,
                            title=scene.section_title,
                            geojson=geojson_data,
                            source_citation=citation,
                            source_url=source_url,
                            reference_date=str(scene.metadata.get("map_reference_date") or "") or None,
                        )
                        scene.metadata["rendered_visual_kind"] = "GEOGRAPHIC_MAP"
                    except (ValueError, OSError) as exc:
                        map_failure = f"GeoJSON map rejected: {exc}"
                else:
                    map_failure = map_failure or (
                        "A project-local GeoJSON FeatureCollection, named features, and a linked external source URL are required."
                    )

                if map_failure:
                    asset = doc_anim.render_process_demonstration(
                        project_id, scene.scene_id, scene.section_title, bullets[:4],
                        citation, duration_sec=clip_dur
                    )
                    scene.metadata["rendered_visual_kind"] = "PROCESS_FALLBACK_NOT_MAP"
                    scene.metadata["visual_data_warning"] = (
                        f"{map_failure} This fallback is a draft only and blocks publication."
                    )
                scene.primary_asset = str(asset)
            elif vtype in {"SPLIT_COMPARISON", "BEFORE_AFTER"}:
                mid = max(1, len(bullets) // 2)
                asset = doc_anim.render_before_after_comparison(
                    project_id, scene.scene_id, scene.section_title,
                    bullets[:mid], bullets[mid:] or bullets[:mid],
                    citation, duration_sec=clip_dur,
                )
                scene.metadata["rendered_visual_kind"] = "BEFORE_AFTER_COMPARISON"
                scene.primary_asset = str(asset)
            elif vtype == "CAUSE_AND_EFFECT":
                cause = str(scene.metadata.get("cause", "")).strip()
                mechanism = str(scene.metadata.get("mechanism", "")).strip()
                effect = str(scene.metadata.get("effect", "")).strip()
                if cause and mechanism and effect and scene.source_citations:
                    asset = doc_anim.render_cause_and_effect(
                        project_id, scene.scene_id, scene.section_title,
                        cause, mechanism, effect, citation, duration_sec=clip_dur,
                    )
                    scene.metadata["rendered_visual_kind"] = "CAUSE_EFFECT"
                else:
                    asset = doc_anim.render_process_demonstration(
                        project_id, scene.scene_id, scene.section_title, bullets[:4],
                        citation, duration_sec=clip_dur
                    )
                    scene.metadata["rendered_visual_kind"] = "PROCESS_FALLBACK_NOT_CAUSE_EFFECT"
                    scene.metadata["visual_data_warning"] = (
                        "Cause-effect visual requested but separately sourced cause, mechanism, and effect "
                        "fields are required. This fallback is a draft only and blocks publication."
                    )
                scene.primary_asset = str(asset)
            elif vtype == "INSTITUTIONAL_DIAGRAM":
                nodes: list[tuple[str, str]] = []
                for bullet in bullets[:3]:
                    role, separator, detail = bullet.partition(":")
                    role = role.strip()
                    detail = detail.strip()
                    if not separator or not role:
                        words = bullet.split()
                        role = " ".join(words[:4]) if words else "Institution"
                        detail = bullet
                    nodes.append((role, detail or bullet))
                if nodes and scene.source_citations:
                    asset = doc_anim.render_institutional_relationship(
                        project_id, scene.scene_id, scene.section_title, nodes, citation, duration_sec=clip_dur
                    )
                    scene.metadata["rendered_visual_kind"] = "INSTITUTIONAL_RELATIONSHIP_DIAGRAM"
                else:
                    asset = doc_anim.render_process_demonstration(
                        project_id, scene.scene_id, scene.section_title, bullets[:4],
                        citation, duration_sec=clip_dur
                    )
                    scene.metadata["rendered_visual_kind"] = "PROCESS_FALLBACK_NOT_INSTITUTIONAL_DIAGRAM"
                    scene.metadata["visual_data_warning"] = (
                        "Institutional relationship diagram requires named entities and linked evidence."
                    )
                scene.primary_asset = str(asset)
            elif vtype in {"FLOWCHART", "STEP_BY_STEP_MECHANISM"}:
                condition = str(scene.metadata.get("flow_condition", "")).strip()
                yes_branch = str(scene.metadata.get("flow_yes", "")).strip()
                no_branch = str(scene.metadata.get("flow_no", "")).strip()
                if condition and yes_branch and no_branch and scene.source_citations:
                    asset = doc_anim.render_flow_diagram(
                        project_id, scene.scene_id, scene.section_title,
                        condition, yes_branch, no_branch, citation, duration_sec=clip_dur
                    )
                    scene.metadata["rendered_visual_kind"] = "FLOWCHART"
                else:
                    asset = doc_anim.render_process_demonstration(
                        project_id, scene.scene_id, scene.section_title, bullets[:4],
                        citation, duration_sec=clip_dur
                    )
                    scene.metadata["rendered_visual_kind"] = "PROCESS_FALLBACK_NOT_FLOWCHART"
                    scene.metadata["visual_data_warning"] = (
                        "Flowchart requested but sourced condition, yes-branch, and no-branch fields are missing. "
                        "This fallback is a draft only and blocks publication."
                    )
                scene.primary_asset = str(asset)
            elif vtype == "SCIENTIFIC_ILLUSTRATION":
                inputs = str(scene.metadata.get("science_inputs", "")).strip()
                transformation = str(scene.metadata.get("science_transformation", "")).strip()
                outputs = str(scene.metadata.get("science_outputs", "")).strip()
                if inputs and transformation and outputs and scene.source_citations:
                    asset = doc_anim.render_scientific_process(
                        project_id, scene.scene_id, scene.section_title,
                        inputs, transformation, outputs, citation, duration_sec=clip_dur
                    )
                    scene.metadata["rendered_visual_kind"] = "SCIENTIFIC_PROCESS"
                else:
                    asset = doc_anim.render_process_demonstration(
                        project_id, scene.scene_id, scene.section_title, bullets[:4],
                        citation, duration_sec=clip_dur
                    )
                    scene.metadata["rendered_visual_kind"] = "PROCESS_FALLBACK_NOT_SCIENTIFIC_PROCESS"
                    scene.metadata["visual_data_warning"] = (
                        "Scientific illustration requested but sourced input, transformation, and output fields "
                        "are required. This fallback is a draft only and blocks publication."
                    )
                scene.primary_asset = str(asset)
            elif vtype in {"DATA_VISUALISATION", "STATISTICAL_COMPARISON"}:
                raw_bars = (scene.metadata or {}).get("chart_data")
                bars = (
                    [item for item in raw_bars if isinstance(item, dict)
                     and str(item.get("label", "")).strip()
                     and isinstance(item.get("value"), (int, float))
                     and not isinstance(item.get("value"), bool)
                     and str(item.get("unit", "")).strip()][:8]
                    if isinstance(raw_bars, list) else []
                )
                units = {str(item.get("unit", "")).strip() for item in bars}
                if len(bars) >= 2 and len(units) == 1 and "" not in units and scene.source_citations:
                    stat_a = (str(bars[0]["label"]), float(bars[0]["value"]))
                    stat_b = (str(bars[1]["label"]), float(bars[1]["value"]))
                    unit = next(iter(units))
                    asset = doc_anim.render_statistical_comparison(
                        project_id, scene.scene_id, scene.section_title,
                        stat_a, stat_b, unit, citation, duration_sec=clip_dur
                    )
                    scene.metadata["rendered_visual_kind"] = "DATA_CHART"
                else:
                    asset = doc_anim.render_process_demonstration(
                        project_id, scene.scene_id, scene.section_title, bullets[:4],
                        citation, duration_sec=clip_dur
                    )
                    scene.metadata["rendered_visual_kind"] = "PROCESS_FALLBACK_NOT_DATA_CHART"
                    scene.metadata["visual_data_warning"] = (
                        "Statistical chart requested but at least two numeric, labelled values with matching units "
                        "and verified source citations are required. This fallback is a draft only and blocks publication."
                    )
                scene.primary_asset = str(asset)
            else:
                asset = doc_anim.render_process_demonstration(
                    project_id, scene.scene_id, scene.section_title, bullets[:4], citation, duration_sec=clip_dur
                )
                if vtype in {"PROCESS_ANIMATION", "PROCESS_DEMONSTRATION", "STEP_BY_STEP_MECHANISM"}:
                    scene.metadata["rendered_visual_kind"] = "PROCESS_DEMONSTRATION"
                else:
                    scene.metadata["rendered_visual_kind"] = "GENERIC_PROCESS_FALLBACK"
                    scene.metadata["visual_data_warning"] = (
                        f"Requested visual type {vtype or 'UNKNOWN'} was not rendered by a matching specialist renderer."
                    )
                scene.primary_asset = str(asset)

        package = PublishingPackageBuilder(project_dir, rights).build_package(
            project_id=project_id, chapter_title=project.chapter_title,
            primary_papers=chapter_map.get("primary_papers", []), scenes=scenes,
            specialist_key=specialist_key, specialist_profile=specialist_profile,
        )
        _write_json(project_dir / "storyboard" / "storyboard.json",
                    [scene.model_dump(mode="json") for scene in scenes])
        report = {"publishing_package": package, "scenes_count": len(scenes),
                  "storyboard_path": str(project_dir / "storyboard" / "storyboard.json")}
        _write_json(paths["visuals"], report)
        return {"status": "COMPLETED", "artifact": str(paths["visuals"]),
                "scenes_count": len(scenes), "storyboard_path": report["storyboard_path"]}

    def _waiting_for_voice(self, project_id: str, project_dir: Path, paths: dict[str, Path],
                           scenes: list[SceneSpec], reason: str,
                           capabilities: dict[str, Any] | None = None) -> dict[str, Any]:
        self.project_mgr.update_status(project_id, ProjectStatus.WAITING_FOR_VOICE)
        qa = QAAuditor(self.conn, project_dir).run_all_checks(project_id)
        ten_gates = TenGateAuditor(self.conn, project_dir).run_ten_gates(project_id, scenes, None)
        report = {"pipeline_status": ProjectStatus.WAITING_FOR_VOICE.value,
                  "voice_wait_reason": reason, "voice_capabilities": capabilities,
                  "qa": qa, "ten_gates": ten_gates}
        _write_json(paths["voice"], report)
        return {"status": "BLOCKED", "pipeline_status": report["pipeline_status"],
                "voice_wait_reason": reason, "artifact": str(paths["voice"])}

    def _stage_voice(self, project_id: str, project_dir: Path, paths: dict[str, Path],
                     voice_path: Path | None, ai_narration: bool) -> dict[str, Any]:
        scenes = self._scene_specs(project_dir)
        rights = AssetRightsLedger(self.conn, project_dir)
        if voice_path is None and not ai_narration:
            return self._waiting_for_voice(
                project_id, project_dir, paths, scenes,
                "No own-voice recording was supplied and AI narration is disabled.",
            )
        if voice_path is not None:
            processor = VoiceAudioProcessor(project_dir, rights_ledger=rights)
            audio = processor.ingest_and_process(project_id, voice_path)
            subtitles = processor.generate_subtitles(scenes, total_audio_sec=audio["duration_sec"])
            narration = Path(audio["processed_file"])
            subtitle_path = Path(subtitles)
            capabilities = None
        else:
            tts = PiperTTSEngine(project_dir, rights_ledger=rights)
            capabilities = tts.detect_voice_capabilities()
            if not capabilities.get("can_synthesize_hindi", False):
                return self._waiting_for_voice(
                    project_id, project_dir, paths, scenes,
                    "No Hindi Piper model or installed Windows SAPI Hindi voice was detected.",
                    capabilities,
                )
            audio = tts.synthesize_scenes(project_id, scenes)
            narration = Path(audio["narration_full_wav"])
            subtitle_path = Path(audio["narration_transcript_srt"])
        actual_duration = float(audio.get("duration_sec") or 0.0)
        estimated_total = sum(max(0.0, scene.estimated_duration_sec) for scene in scenes)
        if actual_duration <= 0 or estimated_total <= 0:
            raise RuntimeError("Voice stage produced an invalid narration duration.")
        scale = actual_duration / estimated_total
        elapsed = 0.0
        for scene in scenes[:-1]:
            scene.estimated_duration_sec = max(
                0.001, round(scene.estimated_duration_sec * scale, 3)
            )
            elapsed += scene.estimated_duration_sec
        # Correct rounding drift on the last scene so the scene timeline ends at
        # the actual narration end, not at the estimated script duration.
        if scenes:
            final_duration = round(actual_duration - elapsed, 3)
            if final_duration <= 0:
                raise RuntimeError("Narration is too short to align all storyboard scenes.")
            scenes[-1].estimated_duration_sec = final_duration
        storyboard_path = project_dir / "storyboard" / "storyboard.json"
        _write_json(
            storyboard_path,
            [scene.model_dump(mode="json") for scene in scenes],
        )
        report = {
            "pipeline_status": "VOICE_READY",
            "audio_report": audio,
            "narration_wav": str(narration),
            "subtitles_srt": str(subtitle_path),
            "voice_capabilities": capabilities,
            "timeline_alignment": {
                "audio_duration_sec": actual_duration,
                "scene_timeline_duration_sec": round(
                    sum(scene.estimated_duration_sec for scene in scenes), 3
                ),
                "method": "SCENE_DURATION_SCALED_TO_ACTUAL_NARRATION",
            },
        }
        _write_json(paths["voice"], report)
        return {"status": "COMPLETED", "artifact": str(paths["voice"]),
                "audio_present": narration.is_file(), "subtitles_present": subtitle_path.is_file()}

    def _stage_render(self, project_id: str, project_dir: Path, paths: dict[str, Path],
                      teaching: dict[str, Any], voice: dict[str, Any]) -> dict[str, Any]:
        scenes = self._scene_specs(project_dir)
        narration = Path(voice["narration_wav"])
        subtitles = Path(voice["subtitles_srt"])
        if not narration.is_file() or not subtitles.is_file():
            raise FileNotFoundError("Voice stage did not produce both narration audio and subtitles.")
        hardware = detect_hardware(project_dir)
        manifest = VideoRenderer(self.conn, project_dir).render_project(
            project_id=project_id, scenes=scenes, narration_wav=narration,
            subtitles_srt=subtitles, preset=hardware.recommended_preset,
            fps=hardware.recommended_fps, resolution=hardware.recommended_resolution,
        )
        project = self.project_mgr.get_project(project_id)
        shorts_candidates = ShortsRenderer.build_candidates(scenes, project.chapter_title)
        shorts_manifest = ShortsRenderer(project_dir).render(
            project_id=project_id,
            candidates=shorts_candidates,
            scenes=scenes,
            narration_wav=narration,
            subtitles_srt=subtitles,
            preset=hardware.recommended_preset,
            fps=hardware.recommended_fps,
        )
        sections = teaching["teaching_summary"]["sections"]
        duration = DurationPlanner(TeachingEngine.WORDS_PER_MINUTE).build_schedule(
            project_dir=project_dir, sections=sections,
            target_duration_min=project.target_duration_min,
            actual_rendered_sec=voice["audio_report"].get("duration_sec"),
        )
        report = {
            "render_manifest": manifest,
            "shorts_manifest": shorts_manifest,
            "duration_schedule": duration,
        }
        _write_json(paths["render"], report)
        return {
            "status": "COMPLETED",
            "artifact": str(paths["render"]),
            "final_video": manifest.get("final_video"),
            "shorts_rendered": shorts_manifest.get("rendered_count", 0),
            "shorts_status": shorts_manifest.get("status"),
        }

    def _stage_qa(self, project_id: str, project_dir: Path, paths: dict[str, Path]) -> dict[str, Any]:
        scenes = self._scene_specs(project_dir)
        manifest = _read_json(paths["render"])["render_manifest"]
        final_video = Path(manifest["final_video"])
        qa = QAAuditor(self.conn, project_dir).run_all_checks(project_id)
        ten_gates = TenGateAuditor(self.conn, project_dir).run_ten_gates(
            project_id, scenes, final_video,
        )
        all_ten_gates_passed = (
            ten_gates.get("all_gates_passed") is True
            and not ten_gates.get("failed_gates")
            and not ten_gates.get("pending_gates")
        )
        final_status = (
            ProjectStatus.APPROVED
            if (
                qa["academic"]["status"] == "PASSED"
                and qa["rights"]["status"] == "PASSED"
                and qa["media"]["status"] == "PASSED"
                and all_ten_gates_passed
                and ten_gates.get("ready_for_publication") == "PASSED"
            )
            else ProjectStatus.NEEDS_REVIEW
        )
        self.project_mgr.update_status(project_id, final_status)
        report = {"pipeline_status": final_status.value, "qa": qa, "ten_gates": ten_gates}
        _write_json(paths["qa"], report)
        business_status = "REVIEW_REQUIRED" if final_status == ProjectStatus.NEEDS_REVIEW else "COMPLETED"
        return {"status": business_status, "pipeline_status": final_status.value,
                "artifact": str(paths["qa"]), "failed_gates": ten_gates.get("failed_gates", [])}

    def run_staged(
        self, project_id: str, notes_files: list[Path] | None = None,
        typed_notes: str = "", voice_path: Path | None = None,
        ai_narration: bool = False,
    ) -> dict[str, Any]:
        """Run the real production stages; reuse completed upstream stages by fingerprint."""
        project = self.project_mgr.get_project(project_id)
        project_dir = Path(project.root_dir).resolve()
        if not project_dir.is_dir():
            raise FileNotFoundError(f"Project workspace does not exist: {project_dir}")
        resolved_notes, typed_notes, resolved_voice = self._resolve_input_bundle(
            project_dir, notes_files, typed_notes, voice_path
        )
        for path in resolved_notes:
            if not path.is_file():
                raise FileNotFoundError(f"Notes file not found: {path}")
        if resolved_voice is not None and not resolved_voice.is_file():
            raise FileNotFoundError(f"Voice recording not found: {resolved_voice}")
        notes_fp, notes_refs = self._file_fingerprint(resolved_notes, typed_notes)
        voice_ref = None
        if resolved_voice is not None:
            voice_ref = {"name": resolved_voice.name, "size": resolved_voice.stat().st_size,
                         "sha256": sha256_file(resolved_voice)}
        paths = self._paths(project_dir)
        project_facts = {
            "chapter_title": project.chapter_title,
            "content_category": project.content_category,
            "cutoff_date": project.cutoff_date,
            "target_duration_min": project.target_duration_min,
            "tts_enabled": project.tts_enabled,
        }
        evidence_fp = _external_evidence_fingerprint(self.conn, project_id)
        academic_fp = _fingerprint({
            "notes": notes_fp,
            "project": project_facts,
            "external_evidence": evidence_fp,
            "version": PIPELINE_STAGE_VERSION,
        })
        teaching_fp = _fingerprint({"academic": academic_fp, "profile_data": SpecialistProfileEngine().version,
                                    "duration": project.target_duration_min})
        visuals_fp = _fingerprint({"teaching": teaching_fp, "visual_schema": PIPELINE_STAGE_VERSION})
        voice_capabilities = None
        if resolved_voice is None and ai_narration:
            voice_capabilities = PiperTTSEngine(project_dir).detect_voice_capabilities()
        voice_fp = _fingerprint({"visuals": visuals_fp, "voice": voice_ref, "ai_narration": ai_narration,
                                 "capabilities": voice_capabilities})
        hardware = detect_hardware(project_dir)
        render_fp = _fingerprint({"visuals": visuals_fp, "voice": voice_fp,
                                  "preset": hardware.recommended_preset, "fps": hardware.recommended_fps,
                                  "resolution": hardware.recommended_resolution})
        manual_review_path = project_dir / "qa" / "manual_review.json"
        manual_review_sha256 = (
            sha256_file(manual_review_path) if manual_review_path.is_file() else None
        )
        qa_fp = _fingerprint({
            "academic": academic_fp,
            "render": render_fp,
            "manual_review_sha256": manual_review_sha256,
            "qa_schema": PIPELINE_STAGE_VERSION,
        })

        handlers = {
            "pipeline_ingestion": lambda payload: self._stage_ingestion(
                project_id, project_dir, paths, resolved_notes, typed_notes),
            "pipeline_academic": lambda payload: self._stage_academic(
                project_id, project_dir, paths, project),
            "pipeline_teaching": lambda payload: self._stage_teaching(
                project_id, project_dir, paths, _read_json(paths["academic"])["chapter_map"]),
            "pipeline_visuals": lambda payload: self._stage_visuals(
                project_id, project_dir, paths, project,
                _read_json(paths["academic"])["chapter_map"], _read_json(paths["teaching"])),
            "pipeline_voice": lambda payload: self._stage_voice(
                project_id, project_dir, paths, resolved_voice, ai_narration),
            "pipeline_render": lambda payload: self._stage_render(
                project_id, project_dir, paths, _read_json(paths["teaching"]), _read_json(paths["voice"])),
            "pipeline_qa": lambda payload: self._stage_qa(project_id, project_dir, paths),
        }
        specs = [
            TaskSpec("ingestion", "PIPELINE_INGESTION", "pipeline_ingestion",
                     payload={"fingerprint": notes_fp, "input_count": len(notes_refs),
                              "typed_notes_present": bool(typed_notes.strip())},
                     max_retries=0, retry_safe=False),
            TaskSpec("academic", "PIPELINE_ACADEMIC_EVIDENCE", "pipeline_academic", depends_on=("ingestion",),
                     payload={"fingerprint": academic_fp}, max_retries=0, retry_safe=False),
            TaskSpec("teaching", "PIPELINE_TEACHING", "pipeline_teaching", depends_on=("academic",),
                     payload={"fingerprint": teaching_fp}, max_retries=0, retry_safe=False),
            TaskSpec("visuals", "PIPELINE_VISUALS", "pipeline_visuals", depends_on=("teaching",),
                     payload={"fingerprint": visuals_fp}, max_retries=0, retry_safe=False),
            TaskSpec("voice", "PIPELINE_VOICE", "pipeline_voice", depends_on=("visuals",),
                     payload={"fingerprint": voice_fp, "voice_supplied": voice_ref is not None,
                              "ai_narration": bool(ai_narration)},
                     max_retries=0, retry_safe=False),
            TaskSpec("render", "PIPELINE_RENDER", "pipeline_render", depends_on=("voice",),
                     payload={"fingerprint": render_fp}, max_retries=0, retry_safe=False),
            TaskSpec("qa", "PIPELINE_QA", "pipeline_qa", depends_on=("render",),
                     payload={"fingerprint": qa_fp}, max_retries=0, retry_safe=False),
        ]
        workflow_id = f"chapter-pipeline:{project_id}"
        self.project_mgr.update_status(project_id, ProjectStatus.PROCESSING)
        scheduler = DependencyScheduler(AgentTaskStore(self.conn), handlers)
        workflow = scheduler.run(workflow_id, specs)
        logical = {row["handler"]: row for row in workflow.get("tasks", [])}
        outputs = {
            key: json.loads(row.get("output_json") or "{}")
            for key, row in logical.items()
        }
        ingestion = _read_json(paths["ingestion"]) if paths["ingestion"].is_file() else {}
        academic = _read_json(paths["academic"]) if paths["academic"].is_file() else {}
        teaching = _read_json(paths["teaching"]) if paths["teaching"].is_file() else {}
        visuals = _read_json(paths["visuals"]) if paths["visuals"].is_file() else {}
        voice = _read_json(paths["voice"]) if paths["voice"].is_file() else {}
        render = _read_json(paths["render"]) if paths["render"].is_file() else {}
        qa = _read_json(paths["qa"]) if paths["qa"].is_file() else {}

        if voice.get("pipeline_status") == ProjectStatus.WAITING_FOR_VOICE.value:
            final_status = ProjectStatus.WAITING_FOR_VOICE.value
        elif workflow.get("status") in {"FAILED", "BLOCKED"}:
            # A blocked required stage is not a successful or indefinitely processing run.
            final_status = ProjectStatus.FAILED.value
        elif qa.get("pipeline_status"):
            final_status = qa["pipeline_status"]
        elif workflow.get("status") == "REVIEW_REQUIRED":
            final_status = ProjectStatus.NEEDS_REVIEW.value
        else:
            final_status = ProjectStatus.PROCESSING.value

        # Keep a prior human approval only while its exact reviewed artifacts and
        # evidence are unchanged. A cached QA report alone cannot preserve approval.
        if (
            project.status == ProjectStatus.APPROVED
            and final_status == ProjectStatus.NEEDS_REVIEW.value
        ):
            approval_path = project_dir / "qa" / "final_10_gate_report.json"
            manual_review_path = project_dir / "qa" / "manual_review.json"
            try:
                approval_report = _read_json(approval_path)
                manual_review = _read_json(manual_review_path)
                scenes = self._scene_specs(project_dir)
                manifest = render.get("render_manifest") or {}
                final_video_value = manifest.get("final_video")
                final_video = Path(final_video_value) if final_video_value else None
                current_fingerprint = TenGateAuditor(
                    self.conn, project_dir
                ).review_fingerprint(project_id, scenes, final_video)
                approval_is_current = (
                    approval_report.get("ready_for_publication") == "PASSED"
                    and manual_review.get("artifact_fingerprint") == current_fingerprint
                    and approval_report.get("gate_details", {}).get("MANUAL_REVIEW", {}).get("review_is_current") is True
                )
                if approval_is_current:
                    final_status = ProjectStatus.APPROVED.value
            except (FileNotFoundError, OSError, ValueError, KeyError, TypeError):
                # Any missing/corrupt approval evidence returns the project to review.
                pass
        if final_status in {
            ProjectStatus.WAITING_FOR_VOICE.value,
            ProjectStatus.APPROVED.value,
            ProjectStatus.NEEDS_REVIEW.value,
            ProjectStatus.FAILED.value,
        }:
            self.project_mgr.update_status(project_id, ProjectStatus(final_status))

        stage_rows = []
        for row in workflow.get("tasks", []):
            stage_rows.append({"task_id": row.get("task_id"), "handler": row.get("handler"),
                               "status": row.get("status"), "attempts": row.get("attempts"),
                               "error": row.get("error")})
        return {
            "project_id": project_id,
            "content_category": project.content_category,
            "status": final_status,
            "specialist_profile": teaching.get("specialist_key"),
            "content_readiness": teaching.get("teaching_summary", {}).get("content_readiness", "UNKNOWN"),
            "matched_pyqs": teaching.get("matched_pyqs", 0),
            "duration_schedule": render.get("duration_schedule") or teaching.get("duration_schedule"),
            "publishing_package": visuals.get("publishing_package"),
            "ingested_docs": ingestion.get("ingested_count", 0),
            "chapter_map": academic.get("chapter_map", {}),
            "evidence_summary": academic.get("evidence_summary", {}),
            "research_discovery": academic.get("research_discovery", {}),
            "scenes_count": visuals.get("scenes_count", 0),
            "recording_script": teaching.get("recording_script"),
            "audio_report": voice.get("audio_report"),
            "render_manifest": render.get("render_manifest"),
            "shorts_manifest": render.get("shorts_manifest"),
            "qa": qa.get("qa") or voice.get("qa"),
            "ten_gates": qa.get("ten_gates") or voice.get("ten_gates"),
            "voice_wait_reason": voice.get("voice_wait_reason"),
            "voice_capabilities": voice.get("voice_capabilities"),
            "pipeline_stages": {"workflow_id": workflow_id, "status": workflow.get("status"),
                                "task_count": workflow.get("task_count"), "completed": workflow.get("completed"),
                                "failed": workflow.get("failed"), "blocked": workflow.get("blocked"),
                                "review_required": workflow.get("review_required"), "tasks": stage_rows},
        }
