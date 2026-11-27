"""FastAPI local desktop web application for UPSC Studio."""

from __future__ import annotations

import json
import re
import requests
import uuid
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from upsc_studio.core.hardware import detect_hardware
from upsc_studio.core.paths import DEFAULT_DB_PATH, DEFAULT_PROJECTS_DIR, sha256_file
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import (
    ClaimVerificationRequest,
    DubLanguageRequest,
    ManualRetryRequest,
    ManualQAReview,
    ProjectCreate,
    ProjectStatus,
    ResearchClaimCreate,
    ResearchDiscoveryRequest,
    ResearchSourceCreate,
    YouTubePublishRequest,
    SceneSpec,
    VerificationStatus,
    utc_now_iso,
)
from upsc_studio.agents.runtime import AgentTaskStore
from upsc_studio.agents.supervisor import ExecutiveProducer
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.qa.ten_gates import TenGateAuditor
from upsc_studio.research.verifier import EvidenceEngine
from upsc_studio.research.discovery import ResearchDiscovery
from upsc_studio.i18n.translation import LANGUAGE_LABELS, TranslationService, TranslationUnavailable
from upsc_studio.audio.processor import VoiceAudioProcessor
from upsc_studio.tts.adapter import PiperTTSEngine
from upsc_studio.graphics.rights import AssetRightsLedger
from upsc_studio.video.renderer import VideoRenderer
from upsc_studio.publishing.youtube_publisher import YouTubePublisher

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
        <input id="p-cutoff" type="date" />
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
        <div class="card" style="background:#0f172a;">
          <h3>Research & Evidence Ledger</h3>
          <p>Register sources first. A URL being present does not prove the claim; review the source text and excerpt yourself.</p>
          <h4>Multilingual Script, Subtitles & Dub</h4>
          <label>Target language</label>
          <select id="dub-language">
            <option value="en">English</option><option value="hi">Hindi</option>
            <option value="bn">Bengali</option><option value="ta">Tamil</option>
            <option value="te">Telugu</option><option value="mr">Marathi</option>
            <option value="gu">Gujarati</option><option value="kn">Kannada</option>
            <option value="ml">Malayalam</option><option value="pa">Punjabi</option>
            <option value="or">Odia</option>
          </select>
          <button class="secondary" onclick="createLanguageOutput()">Translate Script / Subtitles / Dub</button>
          <pre id="i18n-output">Translation provider and target-language voice availability are checked when requested.</pre>
          <h4>Discover Research Sources</h4>
          <label>Search query</label><input id="discovery-query" placeholder="Topic, policy, committee, case or report" />
          <button class="secondary" onclick="discoverResearch()">Find Source Candidates</button>
          <p>Search results are unverified candidates. Current Affairs excludes sources without a publication date or after the project cutoff.</p>
          <h4>Register External Source</h4>
          <label>Source title</label><input id="source-title" placeholder="Report / Act / Paper title" />
          <label>Publisher</label><input id="source-publisher" placeholder="Ministry / Institution / Journal" />
          <label>Source tier</label>
          <select id="source-tier">
            <option value="PRIMARY_OFFICIAL">Primary official</option>
            <option value="ACADEMIC_PEER_REVIEWED">Academic peer reviewed</option>
            <option value="REPUTABLE_NEWS">Reputable news</option>
            <option value="OTHER">Other</option>
          </select>
          <label>HTTP(S) source URL</label><input id="source-url" type="url" placeholder="https://..." />
          <label>Publication date (optional)</label><input id="source-date" placeholder="YYYY-MM-DD" />
          <button class="secondary" onclick="registerSource()">Register Source</button>
          <h4>Register Factual Claim</h4>
          <label>Claim statement (one factual statement)</label><textarea id="claim-statement" rows="2"></textarea>
          <label>Chapter section</label><input id="claim-section" placeholder="Definition / Mechanism / Data" />
          <label>Source ID (optional at first)</label><input id="claim-source-id" placeholder="src_..." />
          <label>Source page / section (optional until reviewed)</label><input id="claim-page" placeholder="Page 12 / Section 3.2" />
          <button class="secondary" onclick="registerClaim()">Register Claim for Review</button>
          <h4>Human Verification Attestation</h4>
          <label>Claim ID</label><input id="verify-claim-id" placeholder="clm_..." />
          <label>Source ID</label><input id="verify-source-id" placeholder="src_..." />
          <label>Exact page / section</label><input id="verify-page" placeholder="Page 12 / Section 3.2" />
          <label>Evidence excerpt (minimum 10 characters)</label><textarea id="verify-excerpt" rows="3"></textarea>
          <label>Reviewer</label><input id="verify-reviewer" placeholder="Name of reviewer" />
          <button onclick="verifyClaim()">Mark Claim VERIFIED after source review</button>
          <pre id="research-output">No research records loaded.</pre>
        </div>
        <div class="card" style="background:#0f172a;">
          <h3>YouTube Publishing</h3>
          <p id="youtube-oauth-status">OAuth connection status not checked.</p>
          <button class="secondary" onclick="refreshYouTubeStatus()">Check YouTube Connection</button>
          <label>Privacy status</label>
          <select id="youtube-privacy">
            <option value="private">Private (default)</option>
            <option value="unlisted">Unlisted</option>
            <option value="public">Public</option>
          </select>
          <label><input type="checkbox" id="youtube-confirm" /> I reviewed the approved final video and explicitly authorise this upload for this run.</label>
          <button onclick="publishVideo()">Upload Approved Video</button>
          <pre id="youtube-output">Upload requires an OAuth token created from your own Google Desktop App credentials.</pre>
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
        <h3>Production Stage Status</h3>
        <div id="pipeline-stages"><p>No production run recorded.</p></div>
        <div class="card" style="background:#0f172a;">
          <h3>Controlled Stage Retry</h3>
          <p>Use only after inspecting partial files. A failed stage and its downstream stages will be reset; completed upstream stages stay intact.</p>
          <label>Reviewer</label><input id="retry-reviewer" placeholder="Reviewer name" />
          <label>Retry reason</label><textarea id="retry-reason" rows="2" placeholder="Describe the failure and fix..."></textarea>
          <label><input type="checkbox" id="retry-inspected" /> I inspected partial output files and understand they may be overwritten.</label>
          <button class="secondary" onclick="prepareRetry()">Prepare Failed-Stage Retry</button>
          <p>After preparation, click Run Production again. Saved notes and voice recordings are reused when no new files are supplied.</p>
        </div>
        <h3>Rendered Shorts</h3>
        <div id="rendered-shorts"><p>No Shorts rendered yet.</p></div>
        <h3>Pipeline Output & Diagnostics</h3>
        <pre id="w-output">Select or run a project to inspect deliverables.</pre>
      </div>
    </div>
  </div>
<script>
let currentProjectId = null;
const cutoffInput = document.getElementById('p-cutoff');
const localNow = new Date();
const localCutoff = new Date(localNow.getTime() - localNow.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
cutoffInput.value = localCutoff;

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
  el.replaceChildren();
  for (const p of list) {
    const item = document.createElement('div');
    item.className = 'proj-item';
    item.addEventListener('click', () => openProject(p.id));
    const name = document.createElement('strong');
    name.textContent = p.name;
    const details = document.createElement('small');
    details.textContent = `${p.content_category} · ${p.chapter_title} — ${p.status}`;
    item.append(name, document.createElement('br'), details);
    el.appendChild(item);
  }
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
  const stageRows = data.pipeline_tasks || [];
  const stageContainer = document.getElementById('pipeline-stages');
  stageContainer.replaceChildren();
  if (!stageRows.length) {
    const empty = document.createElement('p');
    empty.textContent = 'No production stages have been run yet.';
    stageContainer.appendChild(empty);
  } else {
    for (const stage of stageRows) {
      const item = document.createElement('div');
      item.className = 'proj-item';
      const heading = document.createElement('strong');
      heading.textContent = stage.stage_name;
      const status = document.createElement('span');
      const allowedStatuses = ['PENDING', 'RUNNING', 'RETRY_WAIT', 'COMPLETED', 'FAILED', 'BLOCKED', 'SKIPPED', 'REVIEW_REQUIRED'];
      status.textContent = allowedStatuses.includes(stage.status) ? stage.status : 'UNKNOWN';
      status.className = 'badge ' + (allowedStatuses.includes(stage.status) ? stage.status : 'UNKNOWN');
      const meta = document.createElement('small');
      meta.textContent = `Attempts: ${Number(stage.attempts) || 0} · Updated: ${stage.updated_at || 'not started'}`;
      item.append(heading, status, document.createElement('br'), meta);
      if (stage.error) {
        const error = document.createElement('p');
        error.textContent = stage.error;
        item.appendChild(error);
      }
      stageContainer.appendChild(item);
    }
  }
  const shorts = (data.shorts_manifest || {}).shorts || [];
  const shortsContainer = document.getElementById('rendered-shorts');
  shortsContainer.replaceChildren();
  if (!shorts.length) {
    const emptyShorts = document.createElement('p');
    emptyShorts.textContent = 'No Shorts rendered yet.';
    shortsContainer.appendChild(emptyShorts);
  } else {
    for (const shortItem of shorts) {
      const card = document.createElement('div');
      card.className = 'proj-item';
      const title = document.createElement('strong');
      title.textContent = shortItem.title || shortItem.short_id;
      const videoLink = document.createElement('a');
      videoLink.href = `/api/projects/${currentProjectId}/shorts/${encodeURIComponent(shortItem.short_id)}/video`;
      videoLink.textContent = 'Open MP4';
      const srtLink = document.createElement('a');
      srtLink.href = `/api/projects/${currentProjectId}/shorts/${encodeURIComponent(shortItem.short_id)}/subtitles`;
      srtLink.textContent = 'Download SRT';
      card.append(title, document.createElement('br'), videoLink, document.createTextNode(' · '), srtLink);
      shortsContainer.appendChild(card);
    }
  }
  document.getElementById('w-output').textContent = JSON.stringify(data, null, 2);
  await loadResearch();
}

async function refreshYouTubeStatus() {
  const res = await fetch('/api/youtube/status');
  const data = await res.json();
  document.getElementById('youtube-oauth-status').textContent = data.connected
    ? 'YouTube OAuth token file is present. Upload permissions will be checked by Google when used.'
    : 'YouTube is not connected. Run the local OAuth setup command after adding your Google client_secrets.json.';
  document.getElementById('youtube-output').textContent = JSON.stringify(data, null, 2);
}

async function publishVideo() {
  if (!currentProjectId) return;
  if (!document.getElementById('youtube-confirm').checked) {
    alert('Tick the per-run upload confirmation after reviewing the final video.');
    return;
  }
  const approver = document.getElementById('reviewer-name').value.trim();
  const payload = {
    privacy_status: document.getElementById('youtube-privacy').value,
    approver,
    confirm_publish: true
  };
  if (payload.privacy_status === 'public' && !window.confirm('This will publish the video publicly. Continue?')) return;
  const res = await fetch(`/api/projects/${currentProjectId}/publish`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  });
  const data = await res.json();
  document.getElementById('youtube-output').textContent = JSON.stringify(data, null, 2);
  if (!res.ok) alert('Upload not completed: ' + (data.detail || 'Review release gates.'));
}

async function createLanguageOutput() {
  if (!currentProjectId) return;
  const target_language = document.getElementById('dub-language').value;
  const output = document.getElementById('i18n-output');
  output.textContent = 'Checking translation provider and target-language voice models...';
  const res = await fetch(`/api/projects/${currentProjectId}/dub`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({target_language})
  });
  const data = await res.json();
  output.textContent = JSON.stringify(data, null, 2);
  if (!res.ok) alert('Language output not completed: ' + (data.detail || 'Provider unavailable.'));
}

async function loadResearch() {
  if (!currentProjectId) return;
  const res = await fetch(`/api/projects/${currentProjectId}/research`);
  const data = await res.json();
  if (!res.ok) {
    document.getElementById('research-output').textContent = JSON.stringify(data, null, 2);
    return;
  }
  const lines = [
    `Category: ${data.content_category}`,
    'SOURCES:',
    ...data.sources.map(s => `- ${s.id} | ${s.source_tier} | ${s.title} | ${s.url || 'no URL'}`),
    'CLAIMS:',
    ...data.claims.map(cl => `- ${cl.id} | ${cl.status} | ${cl.statement} | source=${cl.source_id || 'none'}`)
  ];
  document.getElementById('research-output').textContent = lines.join(String.fromCharCode(10));
}

async function discoverResearch() {
  if (!currentProjectId) return;
  const query = document.getElementById('discovery-query').value;
  const output = document.getElementById('research-output');
  output.textContent = 'Querying configured discovery providers...';
  const res = await fetch(`/api/projects/${currentProjectId}/research/discover`, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({query, limit: 8})
  });
  const data = await res.json();
  output.textContent = JSON.stringify(data, null, 2);
  if (!res.ok) alert('Research discovery failed: ' + (data.detail || 'Provider error'));
  else await loadResearch();
}

async function registerSource() {
  if (!currentProjectId) return;
  const payload = {
    title: document.getElementById('source-title').value,
    publisher: document.getElementById('source-publisher').value,
    source_tier: document.getElementById('source-tier').value,
    url: document.getElementById('source-url').value,
    pub_date: document.getElementById('source-date').value || null,
    notes: ''
  };
  const res = await fetch(`/api/projects/${currentProjectId}/sources`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok) { alert('Source not registered: ' + (data.detail || 'Invalid source')); return; }
  document.getElementById('claim-source-id').value = data.source_id;
  document.getElementById('verify-source-id').value = data.source_id;
  await loadResearch();
}

async function registerClaim() {
  if (!currentProjectId) return;
  const payload = {
    statement: document.getElementById('claim-statement').value,
    chapter_section: document.getElementById('claim-section').value,
    source_id: document.getElementById('claim-source-id').value || null,
    page_or_section: document.getElementById('claim-page').value || null
  };
  const res = await fetch(`/api/projects/${currentProjectId}/claims`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok) { alert('Claim not registered: ' + (data.detail || 'Invalid claim')); return; }
  document.getElementById('verify-claim-id').value = data.claim_id;
  document.getElementById('verify-source-id').value = payload.source_id || '';
  await loadResearch();
}

async function verifyClaim() {
  if (!currentProjectId) return;
  const claimId = document.getElementById('verify-claim-id').value.trim();
  const payload = {
    source_id: document.getElementById('verify-source-id').value.trim(),
    page_or_section: document.getElementById('verify-page').value,
    evidence_excerpt: document.getElementById('verify-excerpt').value,
    reviewer: document.getElementById('verify-reviewer').value,
    ref_period: null
  };
  const res = await fetch(`/api/projects/${currentProjectId}/claims/${claimId}/verify`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok) { alert('Claim verification not recorded: ' + (data.detail || 'Review failed')); return; }
  alert('Human verification attestation saved. The system did not independently compare semantic support.');
  await loadResearch();
}

async function prepareRetry() {
  if (!currentProjectId) return;
  const payload = {
    reviewer: document.getElementById('retry-reviewer').value,
    reason: document.getElementById('retry-reason').value,
    partial_outputs_inspected: document.getElementById('retry-inspected').checked
  };
  const res = await fetch(`/api/projects/${currentProjectId}/retry`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok) {
    alert('Retry not prepared: ' + (data.detail || 'Review the stage status.'));
    return;
  }
  alert(`Retry prepared from ${data.start_stage}. Click Run Production to execute the reset stages.`);
  await openProject(currentProjectId);
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
        pipeline_tasks: list[dict] = []
        task_table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'agent_tasks'"
        ).fetchone()
        if task_table_exists:
            rows = conn.execute(
                """
                SELECT task_id, handler, status, attempts, error, updated_at, created_at
                FROM agent_tasks
                WHERE workflow_id = ?
                ORDER BY updated_at DESC, created_at DESC
                """,
                (f"chapter-pipeline:{project_id}",),
            ).fetchall()
            latest_by_handler: dict[str, dict] = {}
            stage_names = {
                "pipeline_ingestion": "1. Input ingestion",
                "pipeline_academic": "2. Academic research & evidence",
                "pipeline_teaching": "3. Teaching script & study material",
                "pipeline_visuals": "4. Storyboard & visual production",
                "pipeline_voice": "5. Voice & subtitles",
                "pipeline_render": "6. Video rendering",
                "pipeline_qa": "7. Quality assurance",
            }
            for row in rows:
                handler = row["handler"]
                if handler in stage_names and handler not in latest_by_handler:
                    latest_by_handler[handler] = {
                        "task_id": row["task_id"],
                        "handler": handler,
                        "stage_name": stage_names[handler],
                        "status": row["status"],
                        "attempts": row["attempts"],
                        "error": row["error"],
                        "updated_at": row["updated_at"],
                    }
            pipeline_tasks = [
                latest_by_handler[key]
                for key in stage_names
                if key in latest_by_handler
            ]
        render_stage_path = Path(proj.root_dir) / "workflow" / "stages" / "render.json"
        render_stage = {}
        if render_stage_path.is_file():
            try:
                render_stage = json.loads(render_stage_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                render_stage = {"report_error": "Render-stage report is unreadable."}
        shorts_manifest = render_stage.get("shorts_manifest") or {}
        return {
            "project": proj.model_dump(),
            "qa_gates": gates,
            "ten_gates": ten_gates,
            "claims_count": claims_count,
            "manual_review": manual_review,
            "pipeline_tasks": pipeline_tasks,
            "shorts_manifest": shorts_manifest,
        }

    @app.get("/api/projects/{project_id}/shorts")
    def list_project_shorts(project_id: str) -> dict:
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        manifest_path = Path(proj.root_dir) / "render" / "shorts" / "shorts_manifest.json"
        if not manifest_path.is_file():
            return {"status": "NO_SHORTS_RENDERED", "rendered_count": 0, "shorts": []}
        try:
            report = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail="Shorts manifest is unreadable.") from exc
        return report

    @app.get("/api/projects/{project_id}/shorts/{short_id}/video")
    def download_project_short(project_id: str, short_id: str) -> FileResponse:
        if not re.fullmatch(r"SHORT_\\d{2}", short_id):
            raise HTTPException(status_code=400, detail="Invalid Short ID.")
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        path = Path(proj.root_dir) / "render" / "shorts" / f"{short_id}.mp4"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Rendered Short not found.")
        return FileResponse(path, media_type="video/mp4", filename=f"{proj.slug}_{short_id}.mp4")

    @app.get("/api/projects/{project_id}/shorts/{short_id}/subtitles")
    def download_project_short_subtitles(project_id: str, short_id: str) -> FileResponse:
        if not re.fullmatch(r"SHORT_\\d{2}", short_id):
            raise HTTPException(status_code=400, detail="Invalid Short ID.")
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        path = Path(proj.root_dir) / "render" / "shorts" / f"{short_id}.srt"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Short subtitles not found.")
        return FileResponse(path, media_type="application/x-subrip", filename=f"{short_id}.srt")

    @app.post("/api/projects/{project_id}/run")
    def run_project_pipeline(
        project_id: str,
        typed_notes: str = Form(default=""),
        notes_file: Optional[UploadFile] = File(default=None),
        voice_file: Optional[UploadFile] = File(default=None),
    ) -> dict:
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        if len(typed_notes.encode("utf-8")) > 512 * 1024:
            raise HTTPException(status_code=413, detail="Pasted notes exceed the 512 KB limit.")

        proj_dir = Path(proj.root_dir)
        tmp_dir = proj_dir / "inputs" / "uploads_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        def save_bounded_upload(
            upload: UploadFile,
            allowed_extensions: set[str],
            max_bytes: int,
            label: str,
        ) -> Path:
            original_name = (upload.filename or "").replace("\\", "/").split("/")[-1]
            suffix = Path(original_name).suffix.lower()
            if not original_name or suffix not in allowed_extensions:
                raise HTTPException(
                    status_code=415,
                    detail=f"{label} extension must be one of: {', '.join(sorted(allowed_extensions))}.",
                )
            destination = tmp_dir / f"{uuid.uuid4().hex}{suffix}"
            written = 0
            try:
                with destination.open("wb") as output:
                    while True:
                        chunk = upload.file.read(1024 * 1024)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > max_bytes:
                            raise HTTPException(
                                status_code=413,
                                detail=f"{label} exceeds the {max_bytes // (1024 * 1024)} MB limit.",
                            )
                        output.write(chunk)
                if written == 0:
                    raise HTTPException(status_code=400, detail=f"{label} file is empty.")
                return destination
            except Exception:
                destination.unlink(missing_ok=True)
                raise

        notes_paths: list[Path] = []
        if notes_file and notes_file.filename:
            notes_paths.append(save_bounded_upload(
                notes_file,
                {".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md"},
                100 * 1024 * 1024,
                "Notes file",
            ))

        voice_path: Optional[Path] = None
        if voice_file and voice_file.filename:
            voice_path = save_bounded_upload(
                voice_file,
                {".wav", ".mp3", ".m4a"},
                250 * 1024 * 1024,
                "Voice recording",
            )

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

    @app.post("/api/projects/{project_id}/research/discover")
    def discover_project_research(
        project_id: str, payload: ResearchDiscoveryRequest
    ) -> dict:
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        result = ResearchDiscovery(
            EvidenceEngine(conn, Path(proj.root_dir))
        ).discover(
            project_id=project_id,
            query=payload.query,
            limit=payload.limit,
            cutoff_date=proj.cutoff_date if proj.content_category == "current_affairs" else None,
            require_dated_sources=proj.content_category == "current_affairs",
        )
        return result

    @app.get("/api/i18n/capabilities")
    def get_i18n_capabilities() -> dict:
        translation = TranslationService().capabilities()
        models = PiperTTSEngine.inventory_piper_models()
        return {
            "translation": translation,
            "language_catalogue": [
                {"code": code, "label": label}
                for code, label in LANGUAGE_LABELS.items()
            ],
            "piper_models": models,
            "license_policy": (
                "Dubbing is allowed only when the model entry in voice_licenses.json "
                "contains license, attribution, commercial_use=true and confirmed_by."
            ),
        }

    @app.post("/api/projects/{project_id}/dub")
    def create_language_output(project_id: str, payload: DubLanguageRequest) -> dict:
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        project_dir = Path(proj.root_dir)
        storyboard_path = project_dir / "storyboard" / "storyboard.json"
        if not storyboard_path.is_file():
            raise HTTPException(status_code=409, detail="Run production and generate a storyboard before translation.")
        try:
            scenes = [
                SceneSpec.model_validate(item)
                for item in json.loads(storyboard_path.read_text(encoding="utf-8"))
            ]
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=409, detail=f"Storyboard cannot be translated: {exc}") from exc
        if not scenes:
            raise HTTPException(status_code=409, detail="Storyboard contains no scenes.")

        translator = TranslationService()
        try:
            translation = translator.translate_segments(
                [scene.narration_text for scene in scenes], payload.target_language
            )
        except TranslationUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except (ValueError, requests.RequestException) as exc:
            raise HTTPException(status_code=502, detail=f"Translation provider failed: {exc}") from exc

        translated_texts = translation["translated_texts"]
        translated_scenes = [
            scene.model_copy(update={"narration_text": translated})
            for scene, translated in zip(scenes, translated_texts)
        ]
        script_path = translator.write_translated_script(
            project_dir, proj.chapter_title, scenes, translated_texts,
            payload.target_language, translation["provider"],
        )
        language_dir = project_dir / "subtitles" / payload.target_language
        language_dir.mkdir(parents=True, exist_ok=True)
        subtitle_path = language_dir / "subtitles.srt"
        estimated_duration = sum(max(1.0, scene.estimated_duration_sec) for scene in scenes)
        VoiceAudioProcessor(project_dir).generate_subtitles(
            translated_scenes, total_audio_sec=estimated_duration, output_path=subtitle_path
        )

        tts = PiperTTSEngine(project_dir, rights_ledger=AssetRightsLedger(conn, project_dir))
        matching_models = [
            model for model in tts.discover_piper_models()
            if model["language_code"] == payload.target_language
        ]
        usable_models = [model for model in matching_models if model["usable_for_dubbing"]]
        response: dict[str, Any] = {
            "status": "TRANSLATION_READY_VOICE_MODEL_REQUIRED",
            "translation": {
                **{key: value for key, value in translation.items() if key != "translated_texts"},
                "source_language": "AUTO_DETECTED",
                "human_review_required": True,
            },
            "translated_script": str(script_path),
            "translated_subtitles": str(subtitle_path),
            "matching_piper_models": matching_models,
            "dubbed_audio": None,
            "dubbed_video": None,
        }
        if not usable_models:
            response["voice_requirement"] = (
                "Install a target-language Piper model and verify its licence in "
                "data/tts_models/piper/voice_licenses.json. No substitute voice is used."
            )
        else:
            model = usable_models[0]
            try:
                audio = tts.synthesize_translated_scenes(
                    project_id, scenes, translated_texts,
                    payload.target_language, Path(model["model_path"]),
                )
                response["dubbed_audio"] = audio
                base_video = project_dir / "render" / "final" / "final_video.mp4"
                if base_video.is_file():
                    response["dubbed_video"] = VideoRenderer.render_dubbed_variant(
                        project_dir, payload.target_language, base_video,
                        Path(audio["narration_wav"]), Path(audio["subtitles_srt"]),
                    )
                    response["status"] = "DUBBED_VIDEO_RENDERED_NEEDS_HUMAN_REVIEW"
                else:
                    response["status"] = "DUBBED_AUDIO_READY_VIDEO_RENDER_REQUIRED"
            except (OSError, RuntimeError, ValueError, PermissionError) as exc:
                response["status"] = "VOICE_GENERATION_BLOCKED"
                response["voice_error"] = f"{type(exc).__name__}: {str(exc)[:500]}"

        output_dir = project_dir / "render" / "languages" / payload.target_language
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "language_output_manifest.json").write_text(
            json.dumps(response, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
        return response

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

    @app.post("/api/projects/{project_id}/retry")
    def prepare_pipeline_retry(project_id: str, payload: ManualRetryRequest) -> dict:
        try:
            mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        store = AgentTaskStore(conn)
        inner_workflow_id = f"chapter-pipeline:{project_id}"
        inner_rows = store.list_workflow(inner_workflow_id)
        stage_order = [
            "pipeline_ingestion",
            "pipeline_academic",
            "pipeline_teaching",
            "pipeline_visuals",
            "pipeline_voice",
            "pipeline_render",
            "pipeline_qa",
        ]
        latest: dict[str, dict] = {}
        for row in inner_rows:
            handler = row["handler"]
            previous = latest.get(handler)
            current_time = str(row.get("updated_at") or row.get("created_at") or "")
            previous_time = str(
                (previous or {}).get("updated_at") or (previous or {}).get("created_at") or ""
            )
            if previous is None or current_time >= previous_time:
                latest[handler] = row

        if not latest:
            raise HTTPException(status_code=409, detail="No persisted production stages are available to retry.")

        voice_row = latest.get("pipeline_voice")
        if voice_row and voice_row["status"] == "BLOCKED":
            try:
                voice_output = json.loads(voice_row.get("output_json") or "{}")
            except (TypeError, json.JSONDecodeError):
                voice_output = {}
            if voice_output.get("pipeline_status") == ProjectStatus.WAITING_FOR_VOICE.value:
                raise HTTPException(
                    status_code=409,
                    detail="Voice is the missing input, not a failed task. Upload the creator recording in Run Production to continue.",
                )

        target_handler = next(
            (
                handler for handler in stage_order
                if handler in latest
                and latest[handler]["status"] in {"FAILED", "BLOCKED", "REVIEW_REQUIRED"}
            ),
            None,
        )
        if target_handler is None:
            raise HTTPException(
                status_code=409,
                detail="No failed or blocked production stage exists. Review the current stage and QA status before retrying.",
            )

        try:
            reset_inner = store.retry_from_handler(
                inner_workflow_id,
                target_handler,
                reviewer=payload.reviewer,
                reason=payload.reason,
                partial_outputs_inspected=payload.partial_outputs_inspected,
                ordered_handlers=stage_order,
            )
            outer_row = conn.execute(
                """
                SELECT workflow_id FROM agent_tasks
                WHERE workflow_id LIKE ? AND handler = 'chapter_pipeline'
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (f"production:{project_id}:%",),
            ).fetchone()
            reset_outer: list[str] = []
            if outer_row:
                reset_outer = store.retry_from_handler(
                    outer_row["workflow_id"],
                    "chapter_pipeline",
                    reviewer=payload.reviewer,
                    reason=payload.reason,
                    partial_outputs_inspected=payload.partial_outputs_inspected,
                    ordered_handlers=[
                        "preflight",
                        "chapter_pipeline",
                        "editorial_packaging",
                        "gated_private_publish",
                    ],
                    allow_completed_start=True,
                )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return {
            "status": "RETRY_PREPARED",
            "start_stage": target_handler,
            "reset_inner_tasks": reset_inner,
            "reset_outer_tasks": reset_outer,
            "reviewer": payload.reviewer,
            "next_action": "Run production again. The saved project input bundle will be reused when no new notes are uploaded.",
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

    @app.get("/api/youtube/status")
    def youtube_oauth_status() -> dict:
        return YouTubePublisher().get_oauth_status()

    @app.post("/api/projects/{project_id}/publish")
    def publish_approved_project(
        project_id: str, payload: YouTubePublishRequest
    ) -> dict:
        if not payload.confirm_publish:
            raise HTTPException(
                status_code=409,
                detail="Explicit per-run publication confirmation is required.",
            )
        try:
            proj = mgr.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if proj.status != ProjectStatus.APPROVED:
            raise HTTPException(
                status_code=409,
                detail="Project must have current final human approval before upload.",
            )

        project_dir = Path(proj.root_dir)
        storyboard_path = project_dir / "storyboard" / "storyboard.json"
        final_video = project_dir / "render" / "final" / "final_video.mp4"
        review_path = project_dir / "qa" / "manual_review.json"
        if not storyboard_path.is_file() or not final_video.is_file() or not review_path.is_file():
            raise HTTPException(status_code=409, detail="Final video, storyboard or manual review is missing.")
        try:
            scenes = [
                SceneSpec.model_validate(item)
                for item in json.loads(storyboard_path.read_text(encoding="utf-8"))
            ]
            review = json.loads(review_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=409, detail=f"Release files cannot be validated: {exc}") from exc

        auditor = TenGateAuditor(conn, project_dir)
        current_fingerprint = auditor.review_fingerprint(project_id, scenes, final_video)
        if review.get("artifact_fingerprint") != current_fingerprint:
            mgr.update_status(project_id, ProjectStatus.NEEDS_REVIEW)
            raise HTTPException(
                status_code=409,
                detail="Manual review is stale because reviewed artifacts or evidence changed. Review the current outputs again.",
            )
        report = auditor.run_ten_gates(
            project_id, scenes, final_video, human_approved_by=payload.approver
        )
        if report.get("ready_for_publication") != "PASSED":
            mgr.update_status(project_id, ProjectStatus.NEEDS_REVIEW)
            blockers = [
                f"{name}={status}" for name, status in report.get("gates", {}).items()
                if status != "PASSED"
            ]
            raise HTTPException(
                status_code=409,
                detail="Publication QA is not ready: " + (", ".join(blockers) or "review requirements remain pending"),
            )

        receipt_path = project_dir / "publishing" / "youtube_upload_receipt.json"
        lock_path = project_dir / "publishing" / "youtube_upload_in_progress.json"
        video_sha256 = sha256_file(final_video)
        if receipt_path.is_file():
            try:
                previous_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                previous_receipt = {}
            previous_upload = previous_receipt.get("upload_result", {})
            if (
                previous_upload.get("status") == "UPLOADED"
                and previous_receipt.get("video_sha256") == video_sha256
            ):
                return {
                    **previous_receipt,
                    "status": "ALREADY_UPLOADED",
                    "message": "This exact approved video has already been uploaded. No second upload was attempted.",
                }
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with lock_path.open("x", encoding="utf-8") as descriptor:
                descriptor.write(json.dumps({
                    "project_id": project_id,
                    "requested_by": payload.approver,
                    "requested_at": utc_now_iso(),
                    "video_sha256": video_sha256,
                }))
        except FileExistsError as exc:
            raise HTTPException(
                status_code=409,
                detail="An upload attempt is already in progress or needs reconciliation.",
            ) from exc

        publisher = YouTubePublisher()
        metadata = {
            "video_title": proj.chapter_title[:100],
            "description": (
                f"{proj.content_category.replace('_', ' ').title()} educational documentary. "
                f"Research cutoff: {proj.cutoff_date}. Human-reviewed before upload."
            ),
            "tags": ["Education", "Learning", proj.content_category.replace("_", " ")],
            "chapters": report.get("chapters", []),
        }
        result = publisher.upload_video(
            final_video,
            metadata=metadata,
            qa_passed=True,
            privacy_status=payload.privacy_status,
            human_approved_by=payload.approver,
        )
        receipt = {
            "project_id": project_id,
            "requested_by": payload.approver,
            "requested_privacy": payload.privacy_status,
            "confirmed_this_run": payload.confirm_publish,
            "requested_at": utc_now_iso(),
            "video_sha256": video_sha256,
            "qa_status": report.get("ready_for_publication"),
            "upload_result": result,
        }
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
        lock_path.unlink(missing_ok=True)
        return receipt

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
