"""FastAPI local desktop web application for UPSC Studio."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from upsc_studio.core.hardware import detect_hardware
from upsc_studio.core.paths import DEFAULT_DB_PATH, DEFAULT_PROJECTS_DIR
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import (\n    ClaimVerificationRequest, ManualQAReview, ProjectCreate, ProjectStatus,\n    ResearchClaimCreate, ResearchSourceCreate, SceneSpec, VerificationStatus, utc_now_iso,\n)
from upsc_studio.agents.supervisor import ExecutiveProducer
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.qa.ten_gates import TenGateAuditor\nfrom upsc_studio.research.verifier import EvidenceEngine

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>UPSC Studio — Autonomous GS Production</title>
  <style>
    body { font-family: Segoe UI, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }
    .grid { display: grid; grid-template-columns: 360px 1fr; gap: 20px; max-width: 1400px; margin: auto; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px; margin-bottom: 16px; }
    h1, h2, h3 { margin-top: 0; color: #f59e0b; }
    label { display: block; margin: 8px 0 4px; font-size: 13px; color: #cbd5e1; }
    input, textarea, select { width: 100%; box-sizing: border-box; padding: 8px; border-radius: 6px; border: 1px solid #475569; background: #0f172a; color: #f8fafc; }
    button { background: #f59e0b; color: #0f172a; font-weight: 600; border: none; padding: 10px 14px; border-radius: 6px; cursor: pointer; margin-top: 10px; }
    button.secondary { background: #38bdf8; }
    .badge { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; background: #334155; }
    .PASSED { background: #166534; color: #dcfce7; }
    .FAILED { background: #991b1b; color: #fee2e2; }
    .PENDING, .WAITING_FOR_VOICE { background: #92400e; color: #fef3c7; }
    pre { background: #0f172a; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 12px; max-height: 320px; }
    .proj-item { padding: 8px; border-bottom: 1px solid #334155; cursor: pointer; }
    .proj-item:hover { background: #0f172a; }
    input[type=checkbox] { width: auto; margin-right: 8px; }
  </style>
</head>
<body>
  <div style="max-width:1400px;margin:0 auto 16px;display:flex;justify-content:space-between;align-items:center;">
    <h1>UPSC Studio — Autonomous GS Production System</h1>
    <span id="hw-summary" class="badge">Detecting hardware...</span>
  </div>
  <div class="grid">
    <div>
      <div class="card">
        <h3>New Content Project</h3>
        <label>Project Name</label>
        <input id="p-name" placeholder="e.g. Anti-Defection Law GS2" />
        <label>Chapter / Topic Title</label>
        <input id="p-topic" placeholder="e.g. Anti-Defection Law and Tenth Schedule" />
        <label>Content Category</label>
        <select id="p-category">
          <option value="upsc">UPSC syllabus</option>
          <option value="general_knowledge">General Knowledge</option>
          <option value="current_affairs">Current Affairs</option>
          <option value="deep_dive">Deep Dive</option>
        </select>
        <label>Exam Cycle (UPSC category only)</label>
        <input id="p-cycle" value="UPSC CSE 2026" />
        <label>Research Cutoff Date</label>
        <input id="p-cutoff" value="2026-11-26" />
        <button onclick="createProject()">Create Project</button>
      </div>
      <div class="card">
        <h3>Projects</h3>
        <div id="projects-list">Loading...</div>
      </div>
    </div>
    <div>
      <div class="card" id="workspace-card" style="display:none;">
        <h2 id="w-title">Project</h2>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
          <span id="w-status" class="badge"></span>
          <button class="secondary" onclick="backupCurrent()">Create Backup ZIP</button>
          <button onclick="approveCurrent()">Record Final Human Approval</button>
        </div>
        <div class="card" style="background:#0f172a;">
          <h3>Run Automated Production Pipeline</h3>
          <label>Upload Notes (PDF, DOCX, PPTX, XLSX, TXT, MD)</label>
          <input type="file" id="notes-file" />
          <label>Or Paste Chapter Notes</label>
          <textarea id="typed-notes" rows="4" placeholder="Optional chapter notes..."></textarea>
          <label>Upload Your Own Voice Recording (WAV/MP3 — optional; if omitted, pauses at WAITING_FOR_VOICE)</label>
          <input type="file" id="voice-file" accept=".wav,.mp3,.m4a" />
          <button onclick="runPipeline()">Run Production Pipeline</button>
        </div>
        <h3>QA Gates & Release Readiness</h3>
        <div id="qa-badges" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;"></div>
        <div class="card" style="background:#0f172a;">
          <h3>Manual Quality Review</h3>
          <p id="manual-review-status">No current review is recorded.</p>
          <label><input type="checkbox" id="review-scope" /> I checked the complete topic/syllabus scope and confirmed included, missing and out-of-scope areas.</label>
          <p>Final release remains blocked until these checks are actually reviewed. Tick only after inspecting the generated files/video.</p>
          <label>Reviewer</label>
          <input id="reviewer-name" value="" placeholder="Your name" />
          <label><input type="checkbox" id="review-teaching" /> I reviewed the teaching script for clarity, completeness and unsupported statements.</label>
          <label><input type="checkbox" id="review-visuals" /> I checked scene-by-scene visual relevance, labels, maps, charts and asset attribution.</label>
          <label><input type="checkbox" id="review-subtitles" /> I checked subtitle wording and timing against the narration.</label>
          <label><input type="checkbox" id="review-playback" /> I played the final video and checked beginning, middle, end, audio, transitions and subtitles.</label>
          <label>Review notes (optional)</label>
          <textarea id="review-notes" rows="2" placeholder="List any issues or corrections..."></textarea>
          <button class="secondary" onclick="saveManualReview()">Save Manual Review</button>
        </div>
        <h3>Pipeline Output & Diagnostics</h3>
        <pre id="w-output">Select or run a project to inspect deliverables.</pre>
      </div>
    </div>
  </div>
<script>
let currentProjectId = null;

async function loadHardware() {
  const res = await fetch('/api/hardware');
  const hw = await res.json();
  document.getElementById('hw-summary').textContent =
    `${hw.cpu_model} | ${hw.total_ram_gb} GB RAM | Free: ${hw.free_disk_gb} GB | FFmpeg: ${hw.ffmpeg_path ? 'OK' : 'MISSING'}`;
}

async function loadProjects() {
  const res = await fetch('/api/projects');
  const list = await res.json();
  const el = document.getElementById('projects-list');
  if (!list.length) { el.innerHTML = '<p>No projects yet.</p>'; return; }
  el.innerHTML = list.map(p =>
    `<div class="proj-item" onclick="openProject('${p.id}')">
       <strong>${p.name}</strong><br/>
       <small>${p.content_category} · ${p.chapter_title} — <span class="badge ${p.status}">${p.status}</span></small>
     </div>`
  ).join('');
}

async function createProject() {
  const payload = {
    name: document.getElementById('p-name').value,
    chapter_title: document.getElementById('p-topic').value,
    content_category: document.getElementById('p-category').value,
    exam_cycle: document.getElementById('p-cycle').value,
    cutoff_date: document.getElementById('p-cutoff').value
  };
  const res = await fetch('/api/projects', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  });
  if (!res.ok) { alert('Error creating project'); return; }
  const proj = await res.json();
  await loadProjects();
  await openProject(proj.id);
}

async function openProject(id) {
  currentProjectId = id;
  const res = await fetch(`/api/projects/${id}`);
  const data = await res.json();
  document.getElementById('workspace-card').style.display = 'block';
  document.getElementById('w-title').textContent = `${data.project.name} (${data.project.id})`;
  const st = document.getElementById('w-status');
  st.textContent = data.project.status;
  st.className = `badge ${data.project.status}`;
  const tenGateRows = Object.entries((data.ten_gates || {}).gates || {})
    .map(([gate_name, status]) => ({gate_name, status}));
  const visibleGates = tenGateRows.length ? tenGateRows : (data.qa_gates || []);
  document.getElementById('qa-badges').innerHTML = visibleGates.map(g =>
    `<span class="badge ${g.status}">${g.gate_name}: ${g.status}</span>`
  ).join('');
  const review = data.manual_review || {};
  const checks = review.checks || {};
  const reviewCurrent = review.review_is_current === true;
  document.getElementById('reviewer-name').value = review.reviewer || '';
  document.getElementById('review-notes').value = review.notes || '';
  document.getElementById('review-scope').checked = reviewCurrent && checks.content_scope_coverage === true;
  document.getElementById('manual-review-status').textContent = reviewCurrent
    ? `Current review by ${review.reviewer}`
    : (review.reviewer ? 'Saved review is stale; re-check the current outputs.' : 'No current review is recorded.');
  document.getElementById('review-teaching').checked = reviewCurrent && checks.teaching_clarity === true;
  document.getElementById('review-visuals').checked = reviewCurrent && checks.visual_relevance === true;
  document.getElementById('review-subtitles').checked = reviewCurrent && checks.voice_subtitle_alignment === true;
  document.getElementById('review-playback').checked = reviewCurrent && checks.final_playback_inspection === true;
  document.getElementById('w-output').textContent = JSON.stringify(data, null, 2);
}

async function runPipeline() {
  if (!currentProjectId) return;
  const fd = new FormData();
  fd.append('typed_notes', document.getElementById('typed-notes').value);
  const nf = document.getElementById('notes-file').files[0];
  if (nf) fd.append('notes_file', nf);
  const vf = document.getElementById('voice-file').files[0];
  if (vf) fd.append('voice_file', vf);

  document.getElementById('w-output').textContent = 'Running pipeline... please wait.';
  const res = await fetch(`/api/projects/${currentProjectId}/run`, { method: 'POST', body: fd });
  const result = await res.json();
  await loadProjects();
  await openProject(currentProjectId);
  document.getElementById('w-output').textContent = JSON.stringify(result, null, 2);
}

async function saveManualReview() {
  if (!currentProjectId) return;
  const payload = {
    reviewer: document.getElementById('reviewer-name').value,
    content_scope_coverage: document.getElementById('review-scope').checked,
    teaching_clarity: document.getElementById('review-teaching').checked,
    visual_relevance: document.getElementById('review-visuals').checked,
    voice_subtitle_alignment: document.getElementById('review-subtitles').checked,
    final_playback_inspection: document.getElementById('review-playback').checked,
    notes: document.getElementById('review-notes').value
  };
  const res = await fetch(`/api/projects/${currentProjectId}/review`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok) { alert('Review not saved: ' + (data.detail || 'Unknown error')); return; }
  await openProject(currentProjectId);
  document.getElementById('w-output').textContent = JSON.stringify(data, null, 2);
}

async function backupCurrent() {
  if (!currentProjectId) return;
  const res = await fetch(`/api/projects/${currentProjectId}/backup`, { method: 'POST' });
  const data = await res.json();
  alert('Backup created: ' + data.backup_path);
}

async function approveCurrent() {
  if (!currentProjectId) return;
  const approver = encodeURIComponent(document.getElementById('reviewer-name').value || 'User');
  const res = await fetch(`/api/projects/${currentProjectId}/approve?approver=${approver}`, { method: 'POST' });
  const data = await res.json();
  if (!res.ok) { alert('Cannot approve: ' + data.detail); return; }
  await openProject(currentProjectId);
}

loadHardware();
loadProjects();
</script>
</body>
</html>"""


def create_app(db_path: Path | None = None, projects_root: Path | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    resolved_db = db_path or DEFAULT_DB_PATH
    resolved_projects = projects_root or DEFAULT_PROJECTS_DIR
    conn = init_db(resolved_db)
    mgr = ProjectManager(conn, resolved_projects)

    app = FastAPI(title="UPSC Studio", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return DASHBOARD_HTML

    @app.get("/api/hardware")
    def hardware_info() -> dict:
        return detect_hardware(resolved_projects).to_dict()

    @app.get("/api/projects")
    def list_projects() -> list[dict]:
        return [p.model_dump() for p in mgr.list_projects()]

    @app.post("/api/projects")
    def create_project(payload: ProjectCreate) -> dict:
        return mgr.create_project(payload).model_dump()

    @app.get("/api/projects/{project_id}")
    def get_project_detail(project_id: str) -> dict:
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        gates = [
            dict(r)
            for r in conn.execute("SELECT * FROM qa_gates WHERE project_id = ?", (project_id,)).fetchall()
        ]
        claims_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM claims WHERE project_id = ?", (project_id,)
        ).fetchone()["cnt"]
        review_path = Path(proj.root_dir) / "qa" / "manual_review.json"
        manual_review = {}
        if review_path.is_file():
            try:
                manual_review = json.loads(review_path.read_text(encoding="utf-8"))
                storyboard_path = Path(proj.root_dir) / "storyboard" / "storyboard.json"
                scenes: list[SceneSpec] = []
                if storyboard_path.is_file():
                    raw_scenes = json.loads(storyboard_path.read_text(encoding="utf-8"))
                    scenes = [SceneSpec.model_validate(item) for item in raw_scenes]
                final_video = Path(proj.root_dir) / "render" / "final" / "final_video.mp4"
                auditor = TenGateAuditor(conn, Path(proj.root_dir))
                current_fingerprint = auditor.review_fingerprint(
                    project_id, scenes, final_video if final_video.is_file() else None
                )
                manual_review["review_is_current"] = (
                    manual_review.get("artifact_fingerprint") == current_fingerprint
                )
            except (OSError, ValueError, json.JSONDecodeError):
                manual_review = {
                    "review_error": "Saved manual review is unreadable or its reviewed artifacts changed.",
                    "review_is_current": False,
                }
        ten_gate_path = Path(proj.root_dir) / "qa" / "final_10_gate_report.json"
        ten_gates = {}
        if ten_gate_path.is_file():
            try:
                ten_gates = json.loads(ten_gate_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                ten_gates = {"report_error": "Saved 10-gate report is unreadable."}
        if (
            proj.status == ProjectStatus.APPROVED
            and (
                manual_review.get("review_is_current") is not True
                or ten_gates.get("ready_for_publication") != "PASSED"
            )
        ):
            proj = mgr.update_status(project_id, ProjectStatus.NEEDS_REVIEW)
        return {
            "project": proj.model_dump(),
            "qa_gates": gates,
            "ten_gates": ten_gates,
            "claims_count": claims_count,
            "manual_review": manual_review,
        }

    @app.post("/api/projects/{project_id}/run")
    async def run_project_pipeline(
        project_id: str,
        typed_notes: str = Form(default=""),
        notes_file: Optional[UploadFile] = File(default=None),
        voice_file: Optional[UploadFile] = File(default=None),
    ) -> dict:
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        proj_dir = Path(proj.root_dir)
        tmp_dir = proj_dir / "inputs" / "uploads_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        notes_paths: list[Path] = []
        if notes_file and notes_file.filename:
            dest = tmp_dir / Path(notes_file.filename).name
            with dest.open("wb") as out:
                shutil.copyfileobj(notes_file.file, out)
            notes_paths.append(dest)

        voice_path: Optional[Path] = None
        if voice_file and voice_file.filename:
            vdest = tmp_dir / Path(voice_file.filename).name
            with vdest.open("wb") as out:
                shutil.copyfileobj(voice_file.file, out)
            voice_path = vdest

        producer = ExecutiveProducer(conn, resolved_projects)
        return producer.execute_task_graph(
            project_id=project_id,
            notes_files=notes_paths,
            typed_notes=typed_notes,
            voice_path=voice_path,
            ai_narration=False,
            allow_youtube_upload=False,
            human_publish_approval=False,
        )

    @app.get("/api/projects/{project_id}/research")
    def get_research_ledger(project_id: str) -> dict:
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        sources = [
            dict(row) for row in conn.execute(
                "SELECT * FROM sources WHERE project_id = ? ORDER BY id", (project_id,)
            ).fetchall()
        ]
        claims = [
            dict(row) for row in conn.execute(
                """
                SELECT c.*, s.title AS source_title, s.url AS source_url,
                       s.source_tier AS source_tier
                FROM claims AS c
                LEFT JOIN sources AS s ON s.id = c.source_id
                WHERE c.project_id = ? ORDER BY c.id
                """,
                (project_id,),
            ).fetchall()
        ]
        return {"project_id": proj.id, "content_category": proj.content_category,
                "sources": sources, "claims": claims}

    @app.post("/api/projects/{project_id}/sources")
    def create_research_source(project_id: str, payload: ResearchSourceCreate) -> dict:
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        parsed = urlparse(payload.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=422, detail="Research source URL must use http or https.")
        source_id = EvidenceEngine(conn, Path(proj.root_dir)).add_source(
            project_id=project_id,
            title=payload.title,
            publisher=payload.publisher,
            source_tier=payload.source_tier,
            url=payload.url,
            pub_date=payload.pub_date,
            notes=payload.notes,
        )
        return {"source_id": source_id, "status": "SOURCE_REGISTERED"}

    @app.post("/api/projects/{project_id}/claims")
    def create_research_claim(project_id: str, payload: ResearchClaimCreate) -> dict:
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if payload.source_id:
            source = conn.execute(
                "SELECT id FROM sources WHERE id = ? AND project_id = ?",
                (payload.source_id, project_id),
            ).fetchone()
            if source is None:
                raise HTTPException(status_code=404, detail="Source does not belong to this project.")
        evidence = EvidenceEngine(conn, Path(proj.root_dir))
        claim_id = evidence.add_claim(
            project_id=project_id,
            statement=payload.statement,
            chapter_section=payload.chapter_section,
            status=(
                VerificationStatus.HUMAN_REVIEW_REQUIRED
                if payload.source_id else VerificationStatus.UNSUPPORTED
            ),
            source_id=payload.source_id,
            page_or_section=payload.page_or_section,
            ref_period=payload.ref_period,
            verification_notes="Manually entered; requires review against the cited source.",
        )
        return {"claim_id": claim_id, "status": "HUMAN_REVIEW_REQUIRED"}

    @app.post("/api/projects/{project_id}/claims/{claim_id}/verify")
    def verify_research_claim(
        project_id: str, claim_id: str, payload: ClaimVerificationRequest
    ) -> dict:
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        claim = conn.execute(
            "SELECT id FROM claims WHERE id = ? AND project_id = ?",
            (claim_id, project_id),
        ).fetchone()
        source = conn.execute(
            "SELECT id FROM sources WHERE id = ? AND project_id = ?",
            (payload.source_id, project_id),
        ).fetchone()
        if claim is None:
            raise HTTPException(status_code=404, detail="Claim not found in this project.")
        if source is None:
            raise HTTPException(status_code=404, detail="Source not found in this project.")
        try:
            EvidenceEngine(conn, Path(proj.root_dir)).verify_claim_against_source(
                claim_id=claim_id,
                source_id=payload.source_id,
                page_or_section=payload.page_or_section,
                evidence_excerpt=payload.evidence_excerpt,
                ref_period=payload.ref_period,
                reviewer=payload.reviewer,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "claim_id": claim_id,
            "status": VerificationStatus.VERIFIED.value,
            "verification_method": "HUMAN_ATTESTED_SOURCE_EXCERPT",
            "limitation": "The system records the reviewer attestation; it does not independently prove semantic support.",
        }

    @app.post("/api/projects/{project_id}/review")
    def save_manual_review(project_id: str, payload: ManualQAReview) -> dict:
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        project_dir = Path(proj.root_dir)
        review_path = project_dir / "qa" / "manual_review.json"
        review_path.parent.mkdir(parents=True, exist_ok=True)
        storyboard_path = project_dir / "storyboard" / "storyboard.json"
        scenes: list[SceneSpec] = []
        if storyboard_path.is_file():
            try:
                raw_scenes = json.loads(storyboard_path.read_text(encoding="utf-8"))
                scenes = [SceneSpec.model_validate(item) for item in raw_scenes]
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise HTTPException(status_code=400, detail=f"Storyboard cannot be reviewed: {exc}") from exc
        final_video = project_dir / "render" / "final" / "final_video.mp4"
        final_video_arg = final_video if final_video.is_file() else None
        auditor = TenGateAuditor(conn, project_dir)
        artifact_fingerprint = auditor.review_fingerprint(project_id, scenes, final_video_arg)
        review = {
            "artifact_fingerprint": artifact_fingerprint,
            "reviewer": payload.reviewer,
            "checks": {
                "content_scope_coverage": payload.content_scope_coverage,
                "teaching_clarity": payload.teaching_clarity,
                "visual_relevance": payload.visual_relevance,
                "voice_subtitle_alignment": payload.voice_subtitle_alignment,
                "final_playback_inspection": payload.final_playback_inspection,
            },
            "notes": payload.notes,
            "reviewed_at": utc_now_iso(),
        }
        temp_path = review_path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(review_path)
        response = {"manual_review": review}
        if storyboard_path.is_file():
            response["ten_gates"] = auditor.run_ten_gates(
                project_id, scenes, final_video_arg
            )
        return response

    @app.post("/api/projects/{project_id}/backup")
    def backup_project(project_id: str) -> dict:
        bkp_path = mgr.backup_project(project_id, resolved_projects.parent / "backups")
        return {"backup_path": str(bkp_path)}

    @app.post("/api/projects/{project_id}/approve")
    def approve_project(project_id: str, approver: str = "User") -> dict:
        proj = mgr.get_project(project_id)
        project_dir = Path(proj.root_dir)
        storyboard_path = project_dir / "storyboard" / "storyboard.json"
        if not storyboard_path.is_file():
            raise HTTPException(status_code=400, detail="Storyboard is not available for final review.")
        try:
            raw_scenes = json.loads(storyboard_path.read_text(encoding="utf-8"))
            scenes = [SceneSpec.model_validate(item) for item in raw_scenes]
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Storyboard cannot be reviewed: {exc}") from exc
        final_video = project_dir / "render" / "final" / "final_video.mp4"
        report = TenGateAuditor(conn, project_dir).run_ten_gates(
            project_id, scenes, final_video if final_video.is_file() else None,
            human_approved_by=approver,
        )
        if report["ready_for_publication"] != "PASSED":
            mgr.update_status(project_id, ProjectStatus.NEEDS_REVIEW)
            blockers = [
                f"{name}={status}"
                for name, status in report.get("gates", {}).items()
                if status != "PASSED"
            ]
            raise HTTPException(
                status_code=400,
                detail="Final approval blocked: " + (", ".join(blockers) or "QA requirements are not satisfied."),
            )
        mgr.update_status(project_id, ProjectStatus.APPROVED)
        return {**report, "project_status": ProjectStatus.APPROVED.value}

    @app.get("/api/projects/{project_id}/video")
    def download_video(project_id: str) -> FileResponse:
        proj = mgr.get_project(project_id)
        mp4 = Path(proj.root_dir) / "render" / "final" / "final_video.mp4"
        if not mp4.exists():
            raise HTTPException(status_code=404, detail="Final video not rendered yet.")
        return FileResponse(mp4, media_type="video/mp4", filename=f"{proj.slug}.mp4")

    return app
