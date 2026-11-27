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
          <button class="secondary" onclick="buildDubPack()">Generate 16-Language Dub Pack</button>
          <button onclick="openYouTubeStudio()">Open YouTube Studio — Add Language Tracks</button>
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
        <div class="card" style="background:#0f172a;border:1px solid #10b981;">
          <h3 style="color:#34d399;">Persistent 24-Agent Workflow Runtime</h3>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
            <button onclick="startPersistentWorkflow()" style="background:#10b981;color:#0f172a;">Start 24-Agent DAG Workflow</button>
            <button class="secondary" onclick="pauseWorkflow()">Pause Workflow</button>
            <button class="secondary" onclick="resumeWorkflow()">Resume Workflow</button>
            <button onclick="recoverInterrupted()" style="background:#f59e0b;color:#0f172a;">Recover Interrupted Tasks</button>
            <button class="secondary" onclick="runHealthAudit()">System Health Audit</button>
          </div>
          <div id="workflow-progress" style="margin-top:8px;font-size:13px;color:#94a3b8;">Workflow: Idle</div>
          <div id="workflow-task-badges" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;"></div>
        </div>
        <h3>QA Gates & Release Readiness</h3>
        <div id="qa-badges" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;"></div>
        <h3>Pipeline Output & Diagnostics</h3>
        <pre id="w-output">Select or run a project to inspect deliverables.</pre>
      </div>
    </div>
  </div>

  <div style="max-width:1400px;margin:24px auto;">
    <div class="card" style="background:#1e293b;border:1px solid #3b82f6;">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
        <h2 style="color:#38bdf8;margin:0;">Channel Knowledge Catalogue & Content Gap Auditor</h2>
        <button class="secondary" onclick="loadCatalogue()">Refresh Catalogue</button>
      </div>
      <p style="color:#94a3b8;font-size:13px;margin:8px 0 16px;">
        Complete official UPSC CSE syllabus-to-video coverage graph. Tracks video lifecycle from research to publication with strict quality gate enforcement.
      </p>

      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(160px, 1fr));gap:12px;margin-bottom:16px;" id="cat-stats-cards">
        <div class="card" style="background:#0f172a;text-align:center;"><div style="font-size:24px;font-weight:700;color:#f8fafc;" id="stat-total">-</div><div style="font-size:12px;color:#94a3b8;">Total Syllabus Topics</div></div>
        <div class="card" style="background:#0f172a;text-align:center;"><div style="font-size:24px;font-weight:700;color:#38bdf8;" id="stat-researched">-</div><div style="font-size:12px;color:#94a3b8;">Research Verified</div></div>
        <div class="card" style="background:#0f172a;text-align:center;"><div style="font-size:24px;font-weight:700;color:#a855f7;" id="stat-scripts">-</div><div style="font-size:12px;color:#94a3b8;">Scripts Ready</div></div>
        <div class="card" style="background:#0f172a;text-align:center;"><div style="font-size:24px;font-weight:700;color:#f59e0b;" id="stat-rendered">-</div><div style="font-size:12px;color:#94a3b8;">Videos Rendered</div></div>
        <div class="card" style="background:#0f172a;text-align:center;"><div style="font-size:24px;font-weight:700;color:#10b981;" id="stat-published">-</div><div style="font-size:12px;color:#94a3b8;">Published Videos</div></div>
        <div class="card" style="background:#0f172a;text-align:center;"><div style="font-size:24px;font-weight:700;color:#ef4444;" id="stat-missing">-</div><div style="font-size:12px;color:#94a3b8;">Missing Topics</div></div>
      </div>

      <div style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;">
        <div style="flex:1;min-width:200px;">
          <label>Filter by Paper</label>
          <select id="cat-filter-paper" onchange="filterCatalogue()">
            <option value="">All Papers</option>
            <option value="Mains GS Paper II">Mains GS Paper II (Polity & Constitution)</option>
            <option value="Mains GS Paper I">Mains GS Paper I (History, Geog, Society)</option>
            <option value="Mains GS Paper III">Mains GS Paper III (Economy, Env, S&T)</option>
            <option value="Mains GS Paper IV">Mains GS Paper IV (Ethics & Probity)</option>
            <option value="Prelims GS Paper I">Prelims GS Paper I</option>
            <option value="Prelims CSAT Paper II">Prelims CSAT Paper II</option>
            <option value="Mains Essay">Mains Essay</option>
            <option value="Optional Paper I & II">Optional Subjects</option>
            <option value="Interview / Personality Test">Interview Preparation</option>
            <option value="Current Affairs">Current Affairs</option>
          </select>
        </div>
        <div style="flex:1;min-width:200px;">
          <label>Filter by Status</label>
          <select id="cat-filter-status" onchange="filterCatalogue()">
            <option value="">All Statuses</option>
            <option value="NOT_PLANNED">NOT_PLANNED</option>
            <option value="RESEARCH_VERIFIED">RESEARCH_VERIFIED</option>
            <option value="SCRIPT_READY">SCRIPT_READY</option>
            <option value="VIDEO_RENDERED">VIDEO_RENDERED</option>
            <option value="QA_PASSED">QA_PASSED</option>
            <option value="PUBLISHED">PUBLISHED</option>
            <option value="NEEDS_REVISION">NEEDS_REVISION</option>
          </select>
        </div>
      </div>

      <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;font-size:13px;text-align:left;">
          <thead>
            <tr style="border-bottom:2px solid #475569;color:#cbd5e1;">
              <th style="padding:8px;">Node ID</th>
              <th style="padding:8px;">Paper & Subject</th>
              <th style="padding:8px;">Major Topic</th>
              <th style="padding:8px;">Microtopic & Depth</th>
              <th style="padding:8px;">Status</th>
              <th style="padding:8px;">Video URL / Actions</th>
            </tr>
          </thead>
          <tbody id="catalogue-table-body">
            <tr><td colspan="6" style="padding:12px;text-align:center;color:#94a3b8;">Loading knowledge catalogue...</td></tr>
          </tbody>
        </table>
      </div>

      <div style="margin-top:24px;padding-top:16px;border-top:1px solid #475569;">
        <h3 style="color:#f59e0b;">Channel Content Gap Auditor</h3>
        <p style="font-size:12px;color:#94a3b8;">Scan YouTube channel video inventory against syllabus graph to identify missing topics and generate upgrade plans without duplication.</p>
        <div style="display:flex;gap:12px;margin-bottom:8px;">
          <input id="audit-channel-url" placeholder="https://www.youtube.com/@UPSCStudioChannel" style="flex:2;" />
          <button onclick="runChannelGapAudit()">Run Content Gap Audit</button>
        </div>
        <pre id="audit-output" style="max-height:220px;display:none;">Ready to audit.</pre>
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

async function buildDubPack() {
  if (!currentProjectId) return;
  document.getElementById('w-output').textContent = 'Generating 16-language dub pack... please wait.';
  const res = await fetch(`/api/projects/${currentProjectId}/dub_pack`, { method: 'POST' });
  const data = await res.json();
  document.getElementById('w-output').textContent = JSON.stringify(data, null, 2);
}

function openYouTubeStudio() {
  window.open('https://studio.youtube.com', '_blank');
}

let activeWorkflowRunId = null;

async function startPersistentWorkflow() {
  if (!currentProjectId) { alert('Select a project first.'); return; }
  document.getElementById('workflow-progress').textContent = 'Starting 24-agent DAG workflow...';
  const res = await fetch('/api/workflow/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ project_id: currentProjectId, target_duration_min: 15 })
  });
  const data = await res.json();
  activeWorkflowRunId = data.run_id;
  updateWorkflowUI(data);
  document.getElementById('w-output').textContent = JSON.stringify(data, null, 2);
}

async function pauseWorkflow() {
  if (!activeWorkflowRunId) { alert('No active workflow run.'); return; }
  const res = await fetch(`/api/workflow/${activeWorkflowRunId}/pause`, { method: 'POST' });
  const data = await res.json();
  document.getElementById('workflow-progress').textContent = 'Workflow paused.';
  document.getElementById('w-output').textContent = JSON.stringify(data, null, 2);
}

async function resumeWorkflow() {
  if (!activeWorkflowRunId) { alert('No active workflow run.'); return; }
  document.getElementById('workflow-progress').textContent = 'Resuming workflow...';
  const res = await fetch(`/api/workflow/${activeWorkflowRunId}/resume`, { method: 'POST' });
  const data = await res.json();
  updateWorkflowUI(data);
  document.getElementById('w-output').textContent = JSON.stringify(data, null, 2);
}

async function recoverInterrupted() {
  const res = await fetch('/api/workflow/recover', { method: 'POST' });
  const data = await res.json();
  alert(`Recovered: ${data.recovered_items_count} interrupted task(s).`);
  document.getElementById('w-output').textContent = JSON.stringify(data, null, 2);
}

async function runHealthAudit() {
  const res = await fetch('/api/automation/health');
  const data = await res.json();
  document.getElementById('w-output').textContent = JSON.stringify(data, null, 2);
}

function updateWorkflowUI(data) {
  if (!data || !data.tasks) return;
  document.getElementById('workflow-progress').textContent = `Workflow Status: ${data.status} (${data.progress_percentage}% completed)`;
  const badgesHtml = data.tasks.map(t => {
    let cls = 'PENDING';
    if (t.status === 'COMPLETED') cls = 'PASSED';
    else if (t.status === 'FAILED') cls = 'FAILED';
    else if (t.status === 'EXECUTING') cls = 'WAITING_FOR_VOICE';
    return `<span class="badge ${cls}" title="${t.agent_role}: ${t.status}">${t.agent_id}: ${t.status}</span>`;
  }).join(' ');
  document.getElementById('workflow-task-badges').innerHTML = badgesHtml;
}

async function loadCatalogue() {
  try {
    const summaryRes = await fetch('/api/catalogue/summary');
    const summary = await summaryRes.json();
    document.getElementById('stat-total').textContent = summary.total_entries;
    document.getElementById('stat-researched').textContent = summary.topics_researched;
    document.getElementById('stat-scripts').textContent = summary.topics_with_scripts;
    document.getElementById('stat-rendered').textContent = summary.topics_with_videos;
    document.getElementById('stat-published').textContent = summary.topics_published;
    document.getElementById('stat-missing').textContent = summary.topics_missing_count;
  } catch (err) {
    console.error('Failed to load catalogue summary', err);
  }
  await filterCatalogue();
}

async function filterCatalogue() {
  const paper = document.getElementById('cat-filter-paper').value;
  const status = document.getElementById('cat-filter-status').value;
  const params = new URLSearchParams();
  if (paper) params.append('paper', paper);
  if (status) params.append('status', status);

  try {
    const res = await fetch('/api/catalogue/topics?' + params.toString());
    const topics = await res.json();
    const tbody = document.getElementById('catalogue-table-body');
    if (!topics.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="padding:12px;text-align:center;color:#94a3b8;">No topics match the selected filters.</td></tr>';
      return;
    }
    tbody.innerHTML = topics.map(t => `
      <tr style="border-bottom:1px solid #334155;">
        <td style="padding:8px;font-family:monospace;color:#38bdf8;">${t.node_id}</td>
        <td style="padding:8px;">${t.paper}<br/><small style="color:#94a3b8;">${t.subject}</small></td>
        <td style="padding:8px;font-weight:600;">${t.major_topic}</td>
        <td style="padding:8px;">${t.microtopic}<br/><span class="badge" style="background:#1e293b;color:#a855f7;">${t.required_depth}</span></td>
        <td style="padding:8px;"><span class="badge ${t.catalogue_status}">${t.catalogue_status}</span></td>
        <td style="padding:8px;">${t.published_video_url ? `<a href="${t.published_video_url}" target="_blank" style="color:#38bdf8;text-decoration:none;">Watch Video ↗</a>` : '<span style="color:#64748b;">Not Published</span>'}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to filter catalogue', err);
  }
}

async function runChannelGapAudit() {
  const channelUrl = document.getElementById('audit-channel-url').value || 'https://www.youtube.com/@UPSCStudio';
  const outEl = document.getElementById('audit-output');
  outEl.style.display = 'block';
  outEl.textContent = 'Auditing accessible channel video inventory against syllabus knowledge graph...';

  try {
    const res = await fetch('/api/catalogue/audit_gap', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({channel_url: channelUrl})
    });
    const report = await res.json();
    outEl.textContent = JSON.stringify(report, null, 2);
    await loadCatalogue();
  } catch (err) {
    outEl.textContent = 'Error running gap audit: ' + err.message;
  }
}

loadHardware();
loadProjects();
loadCatalogue();
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

    @app.post("/api/projects/{project_id}/claims/{claim_id}/attest")
    def attest_claim_evidence(project_id: str, claim_id: str, payload: dict) -> dict:
        """Record a reviewer-declared source excerpt; reviewer_id is an audit label, not authentication."""
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        claim = conn.execute(
            "SELECT id, project_id FROM claims WHERE id = ?", (claim_id,)
        ).fetchone()
        if not claim or claim["project_id"] != project_id:
            raise HTTPException(status_code=404, detail="Claim not found in this project.")

        from upsc_studio.research.verifier import EvidenceEngine
        engine = EvidenceEngine(conn, Path(proj.root_dir))
        try:
            engine.verify_claim_against_source(
                claim_id=claim_id,
                source_id=str(payload.get("source_id", "")),
                page_or_section=str(payload.get("page_or_section", "")),
                evidence_excerpt=str(payload.get("evidence_excerpt", "")),
                ref_period=payload.get("ref_period"),
                reviewer_id=str(payload.get("reviewer_id", "")),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "claim_id": claim_id,
            "status": "VERIFIED",
            "attestation_recorded": True,
            "reviewer_id": str(payload.get("reviewer_id", "")).strip(),
            "identity_authenticated": False,
            "notice": "Reviewer ID is an audit label only. The reviewer must inspect the original source and excerpt.",
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

    @app.get("/api/languages")
    def get_languages() -> dict:
        from upsc_studio.languages.registry import LanguageRegistry
        reg = LanguageRegistry()
        return {
            "core_16": [lp.model_dump() for lp in reg.list_core_16()],
            "all_supported": [lp.model_dump() for lp in reg.list_all()],
        }

    @app.post("/api/projects/{project_id}/dub_pack")
    def create_project_dub_pack(project_id: str) -> dict:
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        proj_dir = Path(proj.root_dir)
        sections_file = proj_dir / "teaching" / "sections.json"
        if not sections_file.exists():
            raise HTTPException(status_code=400, detail="Teaching sections not found. Run pipeline first.")

        sections = json.loads(sections_file.read_text(encoding="utf-8"))
        from upsc_studio.publishing.dub_pack import YouTubeDubPackBuilder
        from upsc_studio.languages.registry import CORE_16_LANGUAGES

        builder = YouTubeDubPackBuilder(proj_dir)
        return builder.build_dub_pack(
            chapter_title=proj.chapter_title,
            canonical_script_segments=sections,
            target_languages=list(CORE_16_LANGUAGES.keys()),
            primary_video_path=proj_dir / "render" / "final" / "final_video.mp4",
        )

    # -------------------------------------------------------------
    # PHASE 19: KNOWLEDGE GRAPH, CATALOGUE & GAP AUDITOR ENDPOINTS
    # -------------------------------------------------------------
    from upsc_studio.syllabus.knowledge_graph import KnowledgeGraph
    from upsc_studio.syllabus.knowledge_catalogue import KnowledgeCatalogue, CatalogueStatus
    from upsc_studio.publishing.channel_gap_auditor import ChannelGapAuditor, ChannelVideoItem

    knowledge_graph = KnowledgeGraph()
    knowledge_catalogue = KnowledgeCatalogue(conn, knowledge_graph)
    gap_auditor = ChannelGapAuditor(knowledge_graph, knowledge_catalogue)

    @app.get("/api/knowledge_graph")
    def get_knowledge_graph() -> dict:
        return {
            "breakdown": knowledge_graph.get_coverage_breakdown(),
            "nodes": [n.to_dict() for n in knowledge_graph.nodes.values()],
        }

    @app.get("/api/catalogue/summary")
    def get_catalogue_summary() -> dict:
        return knowledge_catalogue.get_catalogue_summary()

    @app.get("/api/catalogue/topics")
    def get_catalogue_topics(
        paper: str | None = None,
        subject: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        stat_enum = CatalogueStatus(status) if status else None
        return knowledge_catalogue.list_topic_details(paper=paper, subject=subject, status=stat_enum)

    @app.post("/api/catalogue/update_status")
    def update_catalogue_status(payload: dict) -> dict:
        node_id = payload.get("node_id")
        status_str = payload.get("status")
        if not node_id or not status_str:
            raise HTTPException(status_code=400, detail="node_id and status required.")
        try:
            entry = knowledge_catalogue.update_status(
                node_id=node_id,
                new_status=CatalogueStatus(status_str),
                project_id=payload.get("project_id"),
                published_video_url=payload.get("published_video_url"),
                qa_report_id=payload.get("qa_report_id"),
                qa_passed=payload.get("qa_passed", False),
                notes=payload.get("notes", ""),
            )
            return entry.to_dict()
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/catalogue/audit_gap")
    def run_channel_gap_audit(payload: dict) -> dict:
        channel_url = payload.get("channel_url", "https://www.youtube.com/@UPSCStudio")
        custom_videos = payload.get("videos", [])
        video_items = [
            ChannelVideoItem(
                video_id=v.get("video_id", f"vid_{i}"),
                title=v.get("title", ""),
                description=v.get("description", ""),
                published_date=v.get("published_date", "2026-01-01"),
                url=v.get("url", ""),
                transcript=v.get("transcript", ""),
                duration_sec=v.get("duration_sec", 600),
            )
            for i, v in enumerate(custom_videos)
        ]
        report = gap_auditor.audit_channel_videos(channel_url=channel_url, videos=video_items)
        return report.to_dict()

    # -------------------------------------------------------------
    # PHASE 19 (UNIVERSAL): CATEGORIES, FORMATS, MAPPING & COMPLETENESS
    # -------------------------------------------------------------
    from upsc_studio.universal.categories import CategoryRegistry, ContentPillar
    from upsc_studio.universal.formats import FORMAT_REGISTRY, DocumentaryFormatType, FormatSelector
    from upsc_studio.universal.knowledge_mapper import KnowledgeMapper
    from upsc_studio.universal.completeness_auditor import TopicCompletenessAuditor
    from upsc_studio.universal.duplicate_checker import DuplicateExplanationChecker

    universal_cat_registry = CategoryRegistry()
    universal_mapper = KnowledgeMapper(universal_cat_registry)

    @app.get("/api/universal/categories")
    def get_universal_categories() -> dict:
        return {
            "pillars": [p.value for p in ContentPillar],
            "subcategories": [c.to_dict() for c in universal_cat_registry.list_all()],
        }

    @app.get("/api/universal/formats")
    def get_universal_formats() -> list[dict]:
        return [f.to_dict() for f in FORMAT_REGISTRY.values()]

    @app.post("/api/universal/map_topic")
    def map_universal_topic(payload: dict) -> dict:
        title = payload.get("title")
        notes = payload.get("notes", "")
        duration = int(payload.get("target_duration_min", 15))
        if not title:
            raise HTTPException(status_code=400, detail="title required.")
        t_map = universal_mapper.build_topic_map(
            topic_title=title, notes_text=notes, target_duration_min=duration
        )
        return t_map.to_dict()

    @app.post("/api/universal/check_overlap")
    def check_universal_overlap(payload: dict) -> dict:
        title = payload.get("title")
        subtopics = payload.get("subtopics", [])
        if not title:
            raise HTTPException(status_code=400, detail="title required.")
        dup_chk = DuplicateExplanationChecker(conn, resolved_projects)
        res = dup_chk.check_topic_overlap(title, subtopics)
        return res.to_dict()

    # -------------------------------------------------------------
    # PHASE 2: PERSISTENT AGENT RUNTIME & WORKFLOW DAG CONTROLS
    # -------------------------------------------------------------
    from upsc_studio.agents.runtime import AgentWorkflowRuntime
    from upsc_studio.automation.maintenance import SystemMaintenanceEngine

    workflow_runtime = AgentWorkflowRuntime(conn, resolved_projects)
    maintenance_engine = SystemMaintenanceEngine(conn, resolved_projects)

    @app.get("/api/workflow/dag")
    def get_workflow_dag() -> dict:
        return workflow_runtime.get_workflow_dag()

    @app.post("/api/workflow/start")
    def start_project_workflow(payload: dict) -> dict:
        project_id = payload.get("project_id")
        content_pillar = payload.get("content_pillar", "UPSC_CIVIL_SERVICES")
        duration = int(payload.get("target_duration_min", 15))
        if not project_id:
            raise HTTPException(status_code=400, detail="project_id is required.")

        run_id = workflow_runtime.create_or_get_workflow(
            project_id=project_id,
            content_pillar=content_pillar,
            target_duration_min=duration,
        )
        # Execute workflow
        res = workflow_runtime.execute_workflow(run_id)
        return res

    @app.post("/api/workflow/{run_id}/pause")
    def pause_project_workflow(run_id: str) -> dict:
        ok = workflow_runtime.pause_workflow(run_id)
        return {"run_id": run_id, "paused": ok}

    @app.post("/api/workflow/{run_id}/resume")
    def resume_project_workflow(run_id: str) -> dict:
        return workflow_runtime.resume_workflow(run_id)

    @app.get("/api/workflow/{run_id}/status")
    def get_project_workflow_status(run_id: str) -> dict:
        return workflow_runtime.get_workflow_status(run_id)

    @app.post("/api/workflow/recover")
    def recover_interrupted_workflows() -> dict:
        recovered = workflow_runtime.recover_interrupted_workflows()
        return {"recovered_items_count": len(recovered), "recovered_items": recovered}

    @app.get("/api/automation/health")
    def get_system_health() -> dict:
        return maintenance_engine.run_system_health_audit()

    return app
