"""Executive Producer supervising persistent documentary production tasks."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from upsc_studio.agents.contracts import AGENT_REGISTRY, AgentStatus, AgentTaskResult
from upsc_studio.agents.runtime import AgentTaskStore, DependencyScheduler, TaskSpec
from upsc_studio.agents.workers import default_worker_handlers
from upsc_studio.core.paths import sha256_file
from upsc_studio.db.schemas import SceneSpec
from upsc_studio.pipeline.staged import StagedChapterPipeline
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.publishing.editorial_optimizer import EditorialOptimizer
from upsc_studio.publishing.youtube_publisher import YouTubePublisher


class ExecutiveProducer:
    """Runs real production stages through the persistent SQLite task scheduler.

    The pipeline runs seven independently persisted production-stage handlers.
    Registry roles remain REGISTERED unless that exact specialist handler executes;
    stage tasks are not automatically counted as 24 independent specialist agents.
    """

    def __init__(self, conn: sqlite3.Connection, projects_root: Path) -> None:
        self.conn = conn
        self.projects_root = projects_root
        self.mgr = ProjectManager(conn, projects_root)

    @staticmethod
    def run_with_retry(
        agent_id: str,
        fn: Callable[[], dict[str, Any]],
        input_refs: list[str],
        max_retries: int = 2,
        agent_name: str = "",
        dependencies: list[str] | None = None,
    ) -> tuple[AgentTaskResult, Optional[dict[str, Any]]]:
        """Compatibility helper; retry only errors classified as transient."""
        started = time.perf_counter()
        errors: list[str] = []
        deps = dependencies or []
        for attempt in range(max_retries + 1):
            try:
                output = fn()
                return (
                    AgentTaskResult(
                        task_id=f"tsk_{uuid.uuid4().hex[:8]}",
                        agent_id=agent_id,
                        agent_name=agent_name,
                        status=AgentStatus.COMPLETED,
                        dependencies=deps,
                        input_refs=input_refs,
                        output_refs=[
                            str(value) for value in output.values()
                            if isinstance(value, (str, Path))
                        ][:5],
                        execution_time_sec=round(time.perf_counter() - started, 3),
                        retry_count=attempt,
                        verification_status="PENDING_INDEPENDENT_REVIEW",
                    ),
                    output,
                )
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
                transient = isinstance(exc, (TimeoutError, ConnectionError))
                if not transient or attempt >= max_retries:
                    break
                time.sleep(0.2 * (2**attempt))

        return (
            AgentTaskResult(
                task_id=f"tsk_{uuid.uuid4().hex[:8]}",
                agent_id=agent_id,
                agent_name=agent_name,
                status=AgentStatus.FAILED,
                dependencies=deps,
                input_refs=input_refs,
                execution_time_sec=round(time.perf_counter() - started, 3),
                errors=errors,
                retry_count=max(0, len(errors) - 1),
                verification_status="FAILED",
            ),
            None,
        )

    @staticmethod
    def _input_fingerprint(
        project_id: str,
        notes_files: list[Path] | None,
        typed_notes: str,
        voice_path: Path | None,
        ai_narration: bool,
    ) -> str:
        """Hash inputs without storing their text or media bytes in the task payload."""
        inputs: dict[str, Any] = {
            "project_id": project_id,
            "typed_notes_sha256": hashlib.sha256(typed_notes.encode("utf-8")).hexdigest(),
            "ai_narration": bool(ai_narration),
            "notes_files": [],
            "voice": None,
        }
        for path in notes_files or []:
            resolved = Path(path).expanduser().resolve()
            if not resolved.is_file():
                raise FileNotFoundError(f"Notes file not found: {resolved}")
            inputs["notes_files"].append({
                "name": resolved.name,
                "size": resolved.stat().st_size,
                "sha256": sha256_file(resolved),
            })
        if voice_path is not None:
            resolved_voice = Path(voice_path).expanduser().resolve()
            if not resolved_voice.is_file():
                raise FileNotFoundError(f"Voice recording not found: {resolved_voice}")
            inputs["voice"] = {
                "name": resolved_voice.name,
                "size": resolved_voice.stat().st_size,
                "sha256": sha256_file(resolved_voice),
            }
        return hashlib.sha256(
            json.dumps(inputs, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    def execute_task_graph(
        self,
        project_id: str,
        notes_files: list[Path] | None = None,
        typed_notes: str = "",
        voice_path: Optional[Path] = None,
        ai_narration: bool = True,
        youtube_token_path: Path | None = None,
        allow_youtube_upload: bool = False,
        human_publish_approval: bool = False,
    ) -> dict[str, Any]:
        """Execute production, editorial packaging and gated publishing as persisted DAG tasks."""
        project = self.mgr.get_project(project_id)
        project_dir = Path(project.root_dir).resolve()
        if not project_dir.is_dir():
            raise FileNotFoundError(f"Project workspace does not exist: {project_dir}")

        resolved_notes = [Path(item).expanduser().resolve() for item in (notes_files or [])]
        resolved_voice = Path(voice_path).expanduser().resolve() if voice_path is not None else None
        fingerprint = self._input_fingerprint(
            project_id, resolved_notes, typed_notes, resolved_voice, ai_narration
        )
        workflow_id = f"production:{project_id}:{fingerprint[:24]}"
        context: dict[str, Any] = {}

        def preflight_handler(payload: dict[str, Any]) -> dict[str, Any]:
            current = self.mgr.get_project(project_id)
            if Path(current.root_dir).resolve() != project_dir:
                return {"status": "FAILED", "error": "Project root changed during workflow"}
            for path in resolved_notes:
                if not path.is_file():
                    return {"status": "FAILED", "error": f"Notes file disappeared: {path.name}"}
            if resolved_voice is not None and not resolved_voice.is_file():
                return {"status": "FAILED", "error": "Voice recording disappeared"}
            return {
                "status": "COMPLETED",
                "project_id": project_id,
                "category": "not_yet_explicitly_selected",
                "notes_file_count": len(resolved_notes),
                "typed_notes_present": bool(typed_notes.strip()),
                "voice_present": resolved_voice is not None,
                "ai_narration_enabled": bool(ai_narration),
            }

        def production_handler(payload: dict[str, Any]) -> dict[str, Any]:
            # The nested stage DAG persists each real production phase independently.
            # A missing voice is a resumable pause, not a false successful video render.
            pipeline = StagedChapterPipeline(self.conn, self.projects_root)
            result = pipeline.run_staged(
                project_id=project_id,
                notes_files=resolved_notes,
                typed_notes=typed_notes,
                voice_path=resolved_voice,
                ai_narration=ai_narration,
            )
            context["pipe_out"] = result
            return {
                "status": "FAILED" if result.get("status") == "FAILED" else "COMPLETED",
                "project_id": project_id,
                "pipeline_status": result.get("status", "UNKNOWN"),
                "chapter_map": result.get("chapter_map", {}),
                "publishing_package": result.get("publishing_package", {}),
                "render_manifest": result.get("render_manifest"),
                "audio_report": result.get("audio_report"),
                "qa": result.get("qa", {}),
                "ten_gates": result.get("ten_gates", {}),
                "recording_script": result.get("recording_script"),
                "scenes_count": result.get("scenes_count", 0),
                "evidence_summary": result.get("evidence_summary", {}),
                "duration_schedule": result.get("duration_schedule"),
                "matched_pyqs": result.get("matched_pyqs", 0),
                "specialist_profile": result.get("specialist_profile"),
                "voice_wait_reason": result.get("voice_wait_reason"),
                "voice_capabilities": result.get("voice_capabilities"),
                "pipeline_stages": result.get("pipeline_stages", {}),
            }

        def editorial_handler(payload: dict[str, Any]) -> dict[str, Any]:
            dependencies = payload.get("_dependency_outputs", {})
            production = dependencies.get("production", {})
            storyboard_path = project_dir / "storyboard" / "storyboard.json"
            if not storyboard_path.is_file():
                return {"status": "FAILED", "error": "Storyboard artifact is missing"}
            raw_scenes = json.loads(storyboard_path.read_text(encoding="utf-8"))
            scenes = [SceneSpec.model_validate(item) for item in raw_scenes]
            chapter_map = production.get("chapter_map") or {}
            primary_papers = chapter_map.get("primary_papers", [])
            report = EditorialOptimizer().optimize_and_extract_shorts(
                project_dir, project.chapter_title, primary_papers, scenes
            )
            context["editorial"] = report
            return {"status": "COMPLETED", **report}

        def publication_handler(payload: dict[str, Any]) -> dict[str, Any]:
            dependencies = payload.get("_dependency_outputs", {})
            production = dependencies.get("production", {})
            video_info = production.get("render_manifest") or {}
            final_video_value = video_info.get("final_video") if isinstance(video_info, dict) else None
            if not final_video_value:
                return {
                    "status": "SKIPPED",
                    "publisher_status": "PENDING_VIDEO_RENDER",
                    "upload_attempted": False,
                }
            final_video = Path(final_video_value)
            if not final_video.is_file():
                return {
                    "status": "SKIPPED",
                    "publisher_status": "BLOCKED_VIDEO_MISSING",
                    "upload_attempted": False,
                }
            if not (allow_youtube_upload and human_publish_approval):
                return {
                    "status": "SKIPPED",
                    "publisher_status": "BLOCKED_AWAITING_EXPLICIT_PUBLISH_APPROVAL",
                    "upload_attempted": False,
                    "privacy_status": "private",
                }

            qa = production.get("qa") or {}
            ten_gates = production.get("ten_gates") or {}
            qa_passed = (
                production.get("pipeline_status") == "APPROVED"
                and qa.get("academic", {}).get("status") == "PASSED"
                and qa.get("rights", {}).get("status") == "PASSED"
                and qa.get("media", {}).get("status") == "PASSED"
                and ten_gates.get("all_gates_passed") is True
                and not ten_gates.get("failed_gates")
                and not ten_gates.get("pending_gates")
            )
            if not qa_passed:
                return {
                    "status": "SKIPPED",
                    "publisher_status": "BLOCKED_QA_FAILED",
                    "upload_attempted": False,
                }

            metadata = production.get("publishing_package") or {}
            publisher = YouTubePublisher(token_path=youtube_token_path)
            upload = publisher.upload_video(
                final_video,
                metadata,
                qa_passed=True,
                privacy_status="private",
            )
            context["youtube_publish"] = upload
            return {
                "status": "COMPLETED",
                "publisher_status": upload.get("status", "UNKNOWN"),
                "upload_attempted": upload.get("status") in {"UPLOADED", "UPLOAD_FAILED"},
                "video_id": upload.get("video_id"),
                "privacy_status": upload.get("privacy_status", "private"),
                "error": upload.get("error"),
            }

        handlers = default_worker_handlers()
        handlers.update({
            "preflight": preflight_handler,
            "chapter_pipeline": production_handler,
            "editorial_packaging": editorial_handler,
            "gated_private_publish": publication_handler,
        })
        scheduler = DependencyScheduler(AgentTaskStore(self.conn), handlers)
        workflow_payload = {
            "project_id": project_id,
            "has_notes": bool(resolved_notes or typed_notes.strip()),
            "notes_file_count": len(resolved_notes),
            "has_voice": resolved_voice is not None,
            "ai_narration_enabled": bool(ai_narration),
        }
        publication_payload = {
            **workflow_payload,
            "allow_youtube_upload": bool(allow_youtube_upload),
            "human_publish_approval": bool(human_publish_approval),
        }
        specs = [
            TaskSpec(
                task_id="preflight",
                agent_id="EXECUTIVE_PRODUCER",
                handler="preflight",
                payload=workflow_payload,
                required=True,
                max_retries=0,
                retry_safe=False,
            ),
            TaskSpec(
                task_id="production",
                agent_id="DOCUMENTARY_PRODUCTION_PIPELINE",
                handler="chapter_pipeline",
                depends_on=("preflight",),
                payload=workflow_payload,
                required=True,
                max_retries=0,
                retry_safe=False,
            ),
            TaskSpec(
                task_id="editorial",
                agent_id="EDITORIAL_PACKAGING",
                handler="editorial_packaging",
                depends_on=("production",),
                payload=workflow_payload,
                required=False,
                max_retries=1,
                retry_safe=True,
            ),
            TaskSpec(
                task_id="publication",
                agent_id="YOUTUBE_PRIVATE_PUBLISH",
                handler="gated_private_publish",
                depends_on=("production", "editorial"),
                payload=publication_payload,
                required=False,
                max_retries=0,
                retry_safe=False,
            ),
        ]
        workflow = scheduler.run(
            workflow_id, specs, input_fingerprint=fingerprint
        )
        rows = {row["task_id"].split("_")[-1]: row for row in workflow.get("tasks", [])}
        # Runtime task IDs are UUIDs; map them reliably through their stored task_id field.
        task_rows = {row["task_id"]: row for row in workflow.get("tasks", [])}
        by_logical_id: dict[str, dict[str, Any]] = {}
        store = scheduler.store
        for logical_id in ("preflight", "production", "editorial", "publication"):
            match = next(
                (
                    row for row in workflow.get("tasks", [])
                    if row.get("handler") == {
                        "preflight": "preflight",
                        "production": "chapter_pipeline",
                        "editorial": "editorial_packaging",
                        "publication": "gated_private_publish",
                    }[logical_id]
                ),
                None,
            )
            if match is not None:
                by_logical_id[logical_id] = match

        production_row = by_logical_id.get("production", {})
        production_output = json.loads(production_row.get("output_json") or "{}")
        pipe_out = context.get("pipe_out") or production_output
        editorial_row = by_logical_id.get("editorial", {})
        editorial_output = json.loads(editorial_row.get("output_json") or "{}")
        publication_row = by_logical_id.get("publication", {})
        publication_output = json.loads(publication_row.get("output_json") or "{}")

        def registry_state(
            agent_id: str,
            status: AgentStatus,
            task_id: str,
            *,
            output_refs: list[str] | None = None,
            metadata: dict[str, Any] | None = None,
            errors: list[str] | None = None,
        ) -> AgentTaskResult:
            reg = next(item for item in AGENT_REGISTRY if item["id"] == agent_id)
            return AgentTaskResult(
                task_id=task_id,
                agent_id=agent_id,
                agent_name=reg["name"],
                status=status,
                dependencies=reg.get("dependencies", []),
                input_refs=[project_id],
                output_refs=output_refs or [],
                errors=errors or [],
                verification_status="PENDING_INDEPENDENT_REVIEW",
                metadata=metadata or {},
            )

        agent_states: dict[str, AgentTaskResult] = {
            item["id"]: registry_state(
                item["id"],
                AgentStatus.REGISTERED,
                f"registered_{item['id']}",
                metadata={
                    "implementation_status": "NOT_INDEPENDENTLY_EXECUTED",
                    "note": "Core production still contains monolithic stages; no per-role completion is inferred.",
                },
            )
            for item in AGENT_REGISTRY
        }

        if production_row:
            prod_status = production_row.get("status")
            if prod_status == "COMPLETED":
                agent_states["AGENT_01"] = registry_state(
                    "AGENT_01",
                    AgentStatus.COMPLETED,
                    production_row["task_id"],
                    output_refs=[
                        str(pipe_out.get("recording_script"))
                    ] if pipe_out.get("recording_script") else [],
                    metadata={"runtime_task_status": prod_status, "pipeline_status": pipe_out.get("pipeline_status", pipe_out.get("status"))},
                )
            elif prod_status == "REVIEW_REQUIRED":
                agent_states["AGENT_01"] = registry_state(
                    "AGENT_01", AgentStatus.BLOCKED, production_row["task_id"],
                    metadata={"runtime_task_status": prod_status},
                    errors=[production_row.get("error") or "Manual recovery required"],
                )
            else:
                agent_states["AGENT_01"] = registry_state(
                    "AGENT_01", AgentStatus.FAILED, production_row.get("task_id", "production"),
                    metadata={"runtime_task_status": prod_status},
                    errors=[production_row.get("error") or "Production pipeline did not complete"],
                )

        if editorial_row and editorial_row.get("status") == "COMPLETED":
            agent_states["AGENT_20"] = registry_state(
                "AGENT_20", AgentStatus.COMPLETED, editorial_row["task_id"],
                output_refs=[str(project_dir / "publishing" / "editorial_and_shorts_plan.json")],
                metadata={"runtime_task_status": editorial_row.get("status")},
            )
        elif editorial_row and editorial_row.get("status") not in {"PENDING", "RUNNING"}:
            agent_states["AGENT_20"] = registry_state(
                "AGENT_20", AgentStatus.BLOCKED, editorial_row["task_id"],
                metadata={"runtime_task_status": editorial_row.get("status")},
                errors=[editorial_row.get("error") or "Editorial task did not complete"],
            )

        if publication_row:
            pub_status = publication_output.get("publisher_status")
            if pub_status == "UPLOADED":
                mapped_status = AgentStatus.COMPLETED
            elif publication_row.get("status") == "FAILED":
                mapped_status = AgentStatus.FAILED
            else:
                mapped_status = AgentStatus.BLOCKED
            agent_states["AGENT_23"] = registry_state(
                "AGENT_23", mapped_status, publication_row["task_id"],
                metadata={
                    "runtime_task_status": publication_row.get("status"),
                    "publisher_status": pub_status,
                    "upload_attempted": publication_output.get("upload_attempted", False),
                },
                errors=[publication_row.get("error")] if publication_row.get("error") else [],
            )

        event_log = project_dir / "logs" / "agent_events.jsonl"
        event_log.parent.mkdir(parents=True, exist_ok=True)
        with event_log.open("a", encoding="utf-8") as handle:
            for state in agent_states.values():
                handle.write(state.model_dump_json() + "\n")

        result = {
            **(pipe_out if isinstance(pipe_out, dict) else {}),
            "status": (
                pipe_out.get("status", pipe_out.get("pipeline_status", "UNKNOWN"))
                if workflow.get("status") == "COMPLETED"
                else workflow.get("status")
            ),
            "agents_registered": len(AGENT_REGISTRY),
            "agent_states": {key: value.model_dump() for key, value in agent_states.items()},
            "supervisor_task": agent_states["AGENT_01"].model_dump(),
            "editorial_and_shorts": (
                context.get("editorial") or editorial_output
            ),
            "youtube_publish": context.get("youtube_publish") or {
                **publication_output,
                "status": publication_output.get("publisher_status", publication_output.get("status", "UNKNOWN")),
            },
            "workflow": {
                "workflow_id": workflow_id,
                "status": workflow.get("status"),
                "task_count": workflow.get("task_count"),
                "completed": workflow.get("completed"),
                "failed": workflow.get("failed"),
                "blocked": workflow.get("blocked"),
                "review_required": workflow.get("review_required"),
                "tasks": workflow.get("tasks", []),
            },
        }
        return result

    def run_autonomous_factory(
        self,
        project_id: str,
        notes_files: list[Path] | None = None,
        typed_notes: str = "",
        voice_path: Optional[Path] = None,
        ai_narration: bool = True,
        youtube_token_path: Path | None = None,
        allow_youtube_upload: bool = False,
        human_publish_approval: bool = False,
    ) -> dict[str, Any]:
        """Backward-compatible entry point; publishing remains opt-in per run."""
        return self.execute_task_graph(
            project_id=project_id,
            notes_files=notes_files,
            typed_notes=typed_notes,
            voice_path=voice_path,
            ai_narration=ai_narration,
            youtube_token_path=youtube_token_path,
            allow_youtube_upload=allow_youtube_upload,
            human_publish_approval=human_publish_approval,
        )
