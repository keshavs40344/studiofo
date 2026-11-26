"""Executive Producer / Supervisor (AGENT_01) orchestrating the 24-agent documentary factory."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

from upsc_studio.agents.contracts import AGENT_REGISTRY, AgentTaskResult
from upsc_studio.db.schemas import ProjectCreate
from upsc_studio.pipeline.job_manifest import JobManifestManager
from upsc_studio.pipeline.orchestrator import ChapterPipeline
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.publishing.editorial_optimizer import EditorialOptimizer
from upsc_studio.publishing.youtube_publisher import YouTubePublisher


class ExecutiveProducer:
    """Central supervisor coordinating all 24 production agents with retries and checkpoints."""

    def __init__(self, conn: sqlite3.Connection, projects_root: Path) -> None:
        self.conn = conn
        self.projects_root = projects_root
        self.mgr = ProjectManager(conn, projects_root)

    @staticmethod
    def run_with_retry(
        agent_id: str,
        fn: Callable[[], dict],
        input_refs: list[str],
        max_retries: int = 2,
    ) -> tuple[AgentTaskResult, Optional[dict]]:
        """Execute an agent task with exponential backoff retry and structured contract output."""
        t0 = time.perf_counter()
        errors: list[str] = []
        for attempt in range(max_retries + 1):
            try:
                out = fn()
                return (
                    AgentTaskResult(
                        task_id=f"tsk_{uuid.uuid4().hex[:8]}",
                        agent_id=agent_id,
                        input_refs=input_refs,
                        output_refs=[str(v) for v in out.values() if isinstance(v, (str, Path))][:5],
                        status="COMPLETED",
                        execution_time_sec=round(time.perf_counter() - t0, 3),
                        retry_count=attempt,
                        verification_status="VERIFIED",
                    ),
                    out,
                )
            except Exception as exc:
                errors.append(str(exc))
                if attempt < max_retries:
                    time.sleep(0.2 * (2**attempt))

        return (
            AgentTaskResult(
                task_id=f"tsk_{uuid.uuid4().hex[:8]}",
                agent_id=agent_id,
                input_refs=input_refs,
                output_refs=[],
                status="FAILED",
                execution_time_sec=round(time.perf_counter() - t0, 3),
                errors=errors,
                retry_count=max_retries,
                verification_status="FAILED",
            ),
            None,
        )

    def run_autonomous_factory(
        self,
        project_id: str,
        notes_files: list[Path] | None = None,
        typed_notes: str = "",
        voice_path: Optional[Path] = None,
        ai_narration: bool = True,
        youtube_token_path: Path | None = None,
    ) -> dict:
        """Execute full autonomous documentary factory: research -> AI/own voice -> MP4 -> QA -> YouTube check."""
        proj = self.mgr.get_project(project_id)
        proj_dir = Path(proj.root_dir)
        jm = JobManifestManager(proj_dir)

        pipeline = ChapterPipeline(self.conn, self.projects_root)
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
        )

        if task_res.status != "COMPLETED" or pipe_out is None:
            jm.mark_stage("render", "FAILED", {"errors": task_res.errors})
            return {"status": "FAILED", "agent_task": task_res.model_dump()}

        jm.mark_stage("render", "COMPLETED", {"final_video": pipe_out.get("render_manifest", {}).get("final_video")})

        # Editorial Shorts & SEO packaging (AGENT_06 / AGENT_20)
        from upsc_studio.db.schemas import SceneSpec

        sb_path = proj_dir / "storyboard" / "storyboard.json"
        scenes = [SceneSpec(**s) for s in json.loads(sb_path.read_text(encoding="utf-8"))]
        editorial = EditorialOptimizer().optimize_and_extract_shorts(
            proj_dir,
            proj.chapter_title,
            pipe_out["chapter_map"].get("primary_papers", []),
            scenes,
        )

        # YouTube Publishing check (AGENT_23)
        yt = YouTubePublisher(token_path=youtube_token_path)
        final_mp4 = Path(pipe_out["render_manifest"]["final_video"]) if "render_manifest" in pipe_out else None
        qa_passed = (
            pipe_out.get("qa", {}).get("rights", {}).get("status") == "PASSED"
            and pipe_out.get("qa", {}).get("media", {}).get("status") == "PASSED"
        )
        yt_result = (
            yt.upload_video(final_mp4, pipe_out["publishing_package"], qa_passed=qa_passed, privacy_status="private")
            if final_mp4
            else {"status": "PENDING_VIDEO_RENDER"}
        )

        event_log = proj_dir / "logs" / "agent_events.jsonl"
        event_log.parent.mkdir(parents=True, exist_ok=True)
        with event_log.open("a", encoding="utf-8") as f:
            f.write(task_res.model_dump_json() + "\n")

        return {
            **pipe_out,
            "agents_registered": len(AGENT_REGISTRY),
            "supervisor_task": task_res.model_dump(),
            "editorial_and_shorts": editorial,
            "youtube_publish": yt_result,
        }
