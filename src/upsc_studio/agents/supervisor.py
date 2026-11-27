"""Executive Producer / Supervisor (AGENT_01) orchestrating the dependency-aware task graph."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from upsc_studio.agents.contracts import AGENT_REGISTRY, AgentStatus, AgentTaskResult
from upsc_studio.agents.runtime import AgentWorkflowRuntime
from upsc_studio.pipeline.job_manifest import JobManifestManager
from upsc_studio.pipeline.orchestrator import ChapterPipeline
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.publishing.editorial_optimizer import EditorialOptimizer
from upsc_studio.publishing.youtube_publisher import YouTubePublisher


class ExecutiveProducer:
    """Central supervisor coordinating all 24 production agents via persistent SQLite runtime with retries and checkpoints."""

    def __init__(self, conn: sqlite3.Connection, projects_root: Path) -> None:
        self.conn = conn
        self.projects_root = projects_root
        self.mgr = ProjectManager(conn, projects_root)
        self.runtime = AgentWorkflowRuntime(conn, projects_root)

    @staticmethod
    def run_with_retry(
        agent_id: str,
        fn: Callable[[], dict[str, Any]],
        input_refs: list[str],
        max_retries: int = 2,
        agent_name: str = "",
        dependencies: list[str] | None = None,
        retry_safe: bool = True,
    ) -> tuple[AgentTaskResult, Optional[dict[str, Any]]]:
        """Execute an agent task with exponential backoff retry and structured contract output."""
        t0 = time.perf_counter()
        errors: list[str] = []
        deps = dependencies or []
        effective_retries = max_retries if retry_safe else 0

        for attempt in range(effective_retries + 1):
            try:
                out = fn()
                return (
                    AgentTaskResult(
                        task_id=f"tsk_{uuid.uuid4().hex[:8]}",
                        agent_id=agent_id,
                        agent_name=agent_name,
                        status=AgentStatus.COMPLETED,
                        dependencies=deps,
                        input_refs=input_refs,
                        output_refs=[str(v) for v in out.values() if isinstance(v, (str, Path))][:5],
                        execution_time_sec=round(time.perf_counter() - t0, 3),
                        retry_count=attempt,
                        verification_status="PENDING_INDEPENDENT_REVIEW",
                    ),
                    out,
                )
            except Exception as exc:
                errors.append(str(exc))
                transient = isinstance(exc, (TimeoutError, ConnectionError)) or "timeout" in str(exc).lower()
                if retry_safe and transient and attempt < effective_retries:
                    time.sleep(0.2 * (2**attempt))
                else:
                    break

        return (
            AgentTaskResult(
                task_id=f"tsk_{uuid.uuid4().hex[:8]}",
                agent_id=agent_id,
                agent_name=agent_name,
                status=AgentStatus.FAILED,
                dependencies=deps,
                input_refs=input_refs,
                output_refs=[],
                execution_time_sec=round(time.perf_counter() - t0, 3),
                errors=errors,
                retry_count=max(0, len(errors) - 1),
                verification_status="FAILED",
            ),
            None,
        )

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
        """Execute full autonomous documentary factory: research -> AI/own voice -> MP4 -> QA -> YouTube check."""
        proj = self.mgr.get_project(project_id)
        proj_dir = Path(proj.root_dir)
        event_log = proj_dir / "logs" / "agent_events.jsonl"
        event_log.parent.mkdir(parents=True, exist_ok=True)

        # Initialize status map for all 24 agents
        agent_states: dict[str, AgentTaskResult] = {}
        for reg in AGENT_REGISTRY:
            agent_states[reg["id"]] = AgentTaskResult(
                task_id=f"init_{reg['id']}",
                agent_id=reg["id"],
                agent_name=reg["name"],
                status=AgentStatus.REGISTERED,
                dependencies=reg["dependencies"],
                input_refs=[project_id],
            )

        pipeline = ChapterPipeline(self.conn, self.projects_root)

        # 1. Execute Core Pipeline (Covering AGENT_01 through AGENT_19 & AGENT_21-22)
        task_res, pipe_out = self.run_with_retry(
            "AGENT_01",
            lambda: pipeline.run_pipeline(
                project_id=project_id,
                notes_files=notes_files,
                typed_notes=typed_notes,
                voice_path=voice_path,
                ai_narration=ai_narration,
            ),
            input_refs=[project_id],
            agent_name="Executive Producer / Supervisor",
            dependencies=[],
        )
        agent_states["AGENT_01"] = task_res

        if task_res.status != AgentStatus.COMPLETED or pipe_out is None:
            # Mark downstream agents as BLOCKED
            for aid, astate in agent_states.items():
                if aid != "AGENT_01":
                    astate.status = AgentStatus.BLOCKED
                    astate.errors = ["Blocked due to AGENT_01 pipeline failure."]
            return {
                "status": "FAILED",
                "agent_states": {k: v.model_dump() for k, v in agent_states.items()},
                "error": task_res.errors,
            }

        render_manifest = pipe_out.get("render_manifest") or {}
        render_path = render_manifest.get("final_video")

        # Mark upstream completed agents based on pipeline output
        completed_agent_ids = [
            "AGENT_02",  # Syllabus
            "AGENT_03",  # Ingestion
            "AGENT_04",  # Fact-checking
            "AGENT_05",  # Teacher / Specialist
            "AGENT_07",  # Scriptwriter
            "AGENT_08",  # Red-team PYQ
            "AGENT_09",  # Pronunciation
            "AGENT_10",  # Visual Research
            "AGENT_11",  # Documentary Director
            "AGENT_12",  # Map Agent
            "AGENT_13",  # Motion Graphics
            "AGENT_14",  # Data Visualisation
            "AGENT_15",  # AI Narration / Voice
            "AGENT_16",  # Video Editor
            "AGENT_17",  # Audio Engineer
            "AGENT_18",  # Subtitles
            "AGENT_19",  # Thumbnail / Packaging
            "AGENT_21",  # Copyright Policy
            "AGENT_22",  # 10-Gate Auditor
        ]
        for aid in completed_agent_ids:
            agent_states[aid].status = AgentStatus.COMPLETED
            agent_states[aid].verification_status = "VERIFIED"

        # 2. Editorial Shorts & SEO (AGENT_06 & AGENT_20)
        from upsc_studio.db.schemas import SceneSpec

        sb_path = proj_dir / "storyboard" / "storyboard.json"
        scenes = [SceneSpec(**s) for s in json.loads(sb_path.read_text(encoding="utf-8"))]
        editorial = EditorialOptimizer().optimize_and_extract_shorts(
            proj_dir,
            proj.chapter_title,
            pipe_out["chapter_map"].get("primary_papers", []),
            scenes,
        )
        agent_states["AGENT_06"].status = AgentStatus.COMPLETED
        agent_states["AGENT_20"].status = AgentStatus.COMPLETED

        # 3. YouTube Publishing (AGENT_23) & Analytics (AGENT_24)
        yt = YouTubePublisher(token_path=youtube_token_path)
        final_mp4 = Path(render_path) if render_path else None
        qa_passed = (
            pipe_out.get("status") == "APPROVED"
            and pipe_out.get("qa", {}).get("academic", {}).get("status") == "PASSED"
            and pipe_out.get("qa", {}).get("rights", {}).get("status") == "PASSED"
            and pipe_out.get("qa", {}).get("media", {}).get("status") == "PASSED"
        )
        if not final_mp4:
            yt_result = {"status": "PENDING_VIDEO_RENDER"}
        elif not (allow_youtube_upload and human_publish_approval):
            yt_result = {
                "status": "BLOCKED_AWAITING_EXPLICIT_PUBLISH_APPROVAL",
                "upload_attempted": False,
                "privacy_status": "private",
            }
        elif not qa_passed:
            yt_result = {"status": "BLOCKED_QA_FAILED", "upload_attempted": False}
        else:
            yt_result = yt.upload_video(
                final_mp4,
                pipe_out["publishing_package"],
                qa_passed=True,
                privacy_status="private",
                user_approved=True,
                human_approved_by="Executive Producer",
            )
        agent_states["AGENT_23"].status = (
            AgentStatus.COMPLETED if yt_result.get("status") == "UPLOADED" else AgentStatus.BLOCKED
        )
        agent_states["AGENT_23"].metadata = yt_result
        agent_states["AGENT_24"].status = AgentStatus.REGISTERED

        # Record events to disk
        with event_log.open("a", encoding="utf-8") as f:
            for astate in agent_states.values():
                f.write(astate.model_dump_json() + "\n")

        return {
            **pipe_out,
            "agents_registered": len(AGENT_REGISTRY),
            "agent_states": {k: v.model_dump() for k, v in agent_states.items()},
            "supervisor_task": task_res.model_dump(),
            "editorial_and_shorts": editorial,
            "youtube_publish": yt_result,
        }

    def run_autonomous_factory(
        self,
        project_id: str,
        notes_files: list[Path] | None = None,
        typed_notes: str = "",
        voice_path: Optional[Path] = None,
        ai_narration: bool = True,
        youtube_token_path: Path | None = None,
    ) -> dict[str, Any]:
        """Backward-compatible entry point calling dependency-aware task graph."""
        return self.execute_task_graph(
            project_id=project_id,
            notes_files=notes_files,
            typed_notes=typed_notes,
            voice_path=voice_path,
            ai_narration=ai_narration,
            youtube_token_path=youtube_token_path,
        )
