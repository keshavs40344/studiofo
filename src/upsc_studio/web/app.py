"""FastAPI local desktop web application for UPSC Studio."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from upsc_studio.core.hardware import detect_hardware
from upsc_studio.core.paths import DEFAULT_DB_PATH, DEFAULT_PROJECTS_DIR
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate
from upsc_studio.pipeline.orchestrator import ChapterPipeline
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.qa.auditor import QAAuditor

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
        <h3>New UPSC Chapter Project</h3>
        <label>Project Name</label>
        <input id="p-name" placeholder="e.g. Anti-Defection Law GS2" />
        <label>Chapter / Topic Title</label>
        <input id="p-topic" placeholder="e.g. Anti-Defection Law and Tenth Schedule" />
        <label>Exam Cycle</label>
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
       <small>${p.chapter_title} — <span class="badge ${p.status}">${p.status}</span></small>
     </div>`
  ).join('');
}

async function createProject() {
  const payload = {
    name: document.getElementById('p-name').value,
    chapter_title: document.getElementById('p-topic').value,
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
  document.getElementById('qa-badges').innerHTML = (data.qa_gates || []).map(g =>
    `<span class="badge ${g.status}">${g.gate_name}: ${g.status}</span>`
  ).join('');
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

async function backupCurrent() {
  if (!currentProjectId) return;
  const res = await fetch(`/api/projects/${currentProjectId}/backup`, { method: 'POST' });
  const data = await res.json();
  alert('Backup created: ' + data.backup_path);
}

async function approveCurrent() {
  if (!currentProjectId) return;
  const res = await fetch(`/api/projects/${currentProjectId}/approve`, { method: 'POST' });
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
        return {"project": proj.model_dump(), "qa_gates": gates, "claims_count": claims_count}

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

        pipeline = ChapterPipeline(conn, resolved_projects)
        return pipeline.run_pipeline(
            project_id=project_id,
            notes_files=notes_paths,
            typed_notes=typed_notes,
            voice_path=voice_path,
        )

    @app.post("/api/projects/{project_id}/backup")
    def backup_project(project_id: str) -> dict:
        bkp_path = mgr.backup_project(project_id, resolved_projects.parent / "backups")
        return {"backup_path": str(bkp_path)}

    @app.post("/api/projects/{project_id}/approve")
    def approve_project(project_id: str, approver: str = "User") -> dict:
        proj = mgr.get_project(project_id)
        auditor = QAAuditor(conn, Path(proj.root_dir))
        report = auditor.run_all_checks(project_id, human_approved_by=approver)
        if report["publication"]["status"] != "PASSED":
            raise HTTPException(
                status_code=400,
                detail="; ".join(report["publication"]["blocking_issues"]),
            )
        return report

    @app.get("/api/projects/{project_id}/video")
    def download_video(project_id: str) -> FileResponse:
        proj = mgr.get_project(project_id)
        mp4 = Path(proj.root_dir) / "render" / "final" / "final_video.mp4"
        if not mp4.exists():
            raise HTTPException(status_code=404, detail="Final video not rendered yet.")
        return FileResponse(mp4, media_type="video/mp4", filename=f"{proj.slug}.mp4")

    return app
