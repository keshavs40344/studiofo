# UPSC Studio — Mission 5: Observable, Self-Recovering Production Operations Report

**Repository:** `keshavs40344/studiofo`  
**Working Branch:** `phase17/recovery-runtime-integration`  
**Date:** November 2026  
**Auditor/Engine:** UPSC Studio Production & Quality Engineering Agent  
**Verification Status:** 12/12 Operational Scenarios Verified (100%), 47/47 Combined Test Suite Passed, 12/12 Deterministic Agent Evals Passed.

---

## 1. Executive Summary & Operational Goals

In educational documentary production, runtime failures must never cause data corruption, silent data loss, infinite retry loops, or unauthorized publishing. Mission 5 delivers an **observable, self-recovering production operations system** that guarantees failure explainability, idempotent task recovery, and strict fail-closed gating for human release approvals.

### Core Architectural Pillars Implemented

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     Production Operations Architecture                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐ │
│   │ 10-Category Error   │    │ Observable Runtime  │    │ Self-Healing        │ │
│   │ Taxonomy & Policies │───▶│ Monitoring Engine   │───▶│ Recovery Coordinator│ │
│   └─────────────────────┘    └─────────────────────┘    └─────────────────────┘ │
│              │                          │                          │            │
│              ▼                          ▼                          ▼            │
│   ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐ │
│   │ Fail-Closed Retries │    │ Live Task Metrics,  │    │ Interrupted Task    │ │
│   │ (No endless loops)  │    │ RAM/CPU/Disk Usage  │    │ Quarantine & Reset  │ │
│   └─────────────────────┘    └─────────────────────┘    └─────────────────────┘ │
│                                         │                                       │
│                                         ▼                                       │
│                              ┌─────────────────────┐                            │
│                              │ Production Control  │                            │
│                              │ Centre & Dashboard  │                            │
│                              └─────────────────────┘                            │
└─────────────────────────────────────────────────────────────────────────────────┘
```

1. **10-Category Error Taxonomy:** Classifies every runtime and domain error into 10 explicit categories with deterministic retry policies (`is_retryable`, `requires_human_review`, and actionable `recovery_suggestion`).
2. **Observable Runtime Monitoring:** Real-time tracking of project status, stage progress, task timestamps (`started_at`, `finished_at`), precise duration measurements (`duration_sec`), attempt counts, error categories, output artifacts, and system resource consumption (CPU %, memory RSS MB, disk free GB).
3. **Self-Healing Recovery Coordinator:** Automated detection and quarantining of interrupted tasks left in `RUNNING` state after process termination or power loss; safe checkpoint restoration; temporary artifact cleanup (`*.tmp`, partial video fragments); partial rendering recovery (scene-level memoization); SQLite database integrity verification (`PRAGMA integrity_check`, `PRAGMA foreign_key_check`); and automated stale approval invalidation upon content drift.
4. **Production Control Centre:** Web dashboard backed by 4 real operational endpoints (`/operations`, `/recover`, `/cleanup-temp`, `/verify-db`) where every button executes a concrete backend action.

---

## 2. 10-Category Error Classification Taxonomy & Retry Policy

To prevent endless retry loops on permanent failures, errors are strictly categorized:

| # | Category | Description / Triggers | `is_retryable` | `requires_human_review` | Actionable Policy |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **1** | `TRANSIENT_EXTERNAL` | Network timeouts, socket resets, API 503/429 | **Yes** | No | Safe auto-retry up to `max_retries` with exponential backoff. |
| **2** | `MISSING_DEPENDENCY` | Missing FFmpeg, Piper voice model, fonts, Tesseract | **No** | **Yes** | Fails closed; halts downstream stages until tool is installed on system PATH. |
| **3** | `INVALID_USER_INPUT` | Malformed manifest, bad date format, unsupported file | **No** | **Yes** | Immediate failure; prompts user to supply valid inputs. |
| **4** | `RESEARCH_VALIDATION_FAILURE` | Prompt injection, contradictory facts, unverified claims | **No** | **Yes** | Human review required; blocks automated narration. |
| **5** | `ACADEMIC_QUALITY_FAILURE` | Syllabus gaps, prerequisite omission, incomplete chapter | **No** | **Yes** | Fails closed; requires curriculum expansion. |
| **6** | `RIGHTS_FAILURE` | Unverified license, copyright alert, unknown origin | **No** | **Yes** | Blocks publishing; requires license proof or asset replacement. |
| **7** | `AUDIO_VIDEO_FAILURE` | Audio clipping (>0.985), dead air (>3.0s), render error | **No** | **Yes** | Requires audio re-recording or video parameter adjustment. |
| **8** | `FILESYSTEM_FAILURE` | Disk space < 1.0 GB, permission denied, I/O error | **No** | **Yes** | Fails closed; protects host filesystem integrity. |
| **9** | `DATABASE_FAILURE` | SQLite lock/busy vs foreign key / schema violation | **Conditional** | **Conditional** | Transient SQLite locks are retryable with backoff; structural violations require DB repair. |
| **10** | `AUTHENTICATION_FAILURE` | YouTube OAuth missing, token expired, 401/403 | **No** | **Yes** | Fails closed; requires user re-authorization. |

### Enforced Invariant
> **No automatic retry may bypass academic, rights, or human publication approvals.**  
> Permanent failures (`MISSING_DEPENDENCY`, `INVALID_USER_INPUT`, `RESEARCH_VALIDATION_FAILURE`, `RIGHTS_FAILURE`, `AUTHENTICATION_FAILURE`) are never endlessly retried.

---

## 3. Observable Runtime Monitoring Engine

Module: [`src/upsc_studio/pipeline/monitoring.py`](file:///c:/Users/HP/Downloads/NovaStream/upsc_studio/src/upsc_studio/pipeline/monitoring.py)

### Telemetry & Tracking Capabilities
- **Live Project Status:** Real-time state (`NOT_STARTED`, `PROCESSING`, `WAITING_FOR_VOICE`, `NEEDS_REVIEW`, `APPROVED`, `EXPORTED`, `FAILED`).
- **7 Production Stages:** Detailed breakdown across `pipeline_ingestion`, `pipeline_academic`, `pipeline_teaching`, `pipeline_visuals`, `pipeline_voice`, `pipeline_render`, `pipeline_qa`.
- **Task Durations & Timestamps:** Wall-clock duration (`duration_sec`) calculated from ISO UTC `started_at` and `finished_at`.
- **Resource Usage Sampling:** Measures system CPU %, process CPU %, process memory RSS (MB), total available memory (GB), and free disk space (GB) using non-blocking calls (`psutil`).
- **Artifact References:** Index of all durable artifacts produced in `workflow/stages/` (e.g. `ingestion.json`, `academic.json`, `teaching.json`, `visuals.json`, `voice.json`, `render.json`, `qa.json`).
- **Last Checkpoint:** Recovers last valid stage checkpoint from SQLite `agent_checkpoints`.
- **Recovery Eligibility:** Evaluates whether an automated resume or reviewed retry is appropriate.

---

## 4. Self-Healing Recovery Coordinator

Module: [`src/upsc_studio/pipeline/recovery.py`](file:///c:/Users/HP/Downloads/NovaStream/upsc_studio/src/upsc_studio/pipeline/recovery.py)

### Automated Recovery Capabilities

1. **Interrupted Task Detection & Quarantining:**
   - Detects tasks left in `RUNNING` due to sudden termination, power failure, or process crash.
   - Transitions them to `REVIEW_REQUIRED` with error classification (`FILESYSTEM_FAILURE`).
   - Prevents unmonitored blind re-execution of partially completed tasks with unknown side effects.
2. **Workspace Hygiene & Temporary Artifact Cleanup:**
   - Traverses workspace and cleans orphaned `*.tmp` and `*.partial` files.
   - Computes recovered bytes and records a clean status log.
3. **Database Consistency Verification:**
   - Runs `PRAGMA integrity_check;` and `PRAGMA foreign_key_check;`.
   - Surfaces structural or relational anomalies without corrupting production tables.
4. **Stale Approval Invalidation:**
   - If lesson notes, claims, script, storyboard, or video file change after human approval (`APPROVED`), the coordinator calculates a cryptographic review fingerprint (`TenGateAuditor.review_fingerprint`).
   - If drift is detected, approval is immediately invalidated: status is reset from `APPROVED` to `NEEDS_REVIEW` and an `APPROVAL_INVALIDATED` audit event is recorded.
5. **Partial Rendering Recovery:**
   - Validates existing scene MP4 files against asset SHA-256 and duration in SQLite `render_jobs`.
   - Reuses completed scenes from cache without re-rendering, dramatically reducing CPU load on Windows laptops.
6. **Duplicate Publish Prevention:**
   - Queries `qa_gates` for `YOUTUBE_PUBLISHED` with matching video SHA-256.
   - Blocks duplicate uploads if the exact video has already been published.

---

## 5. Production Control Centre & Real Backend Operations

Module: [`src/upsc_studio/web/app.py`](file:///c:/Users/HP/Downloads/NovaStream/upsc_studio/src/upsc_studio/web/app.py)

The Web Dashboard now integrates an active **Production Control Centre & Operations** card where every button connects directly to a backend FastAPI route:

```
[ Auto-Recover / Quarantine ] ──▶ POST /api/projects/{id}/recover
[ Clean Temp Files ]          ──▶ POST /api/projects/{id}/cleanup-temp
[ Verify DB Integrity ]       ──▶ POST /api/projects/{id}/verify-db
[ Refresh Operations Status ] ──▶ GET  /api/projects/{id}/operations
```

- **Live UI Feedback:** Alerts the user with actual numbers of quarantined tasks, cleaned files, freed bytes, and database integrity status.
- **Fail-Closed Gate Enforcement:** The approval and publish buttons enforce ten-gate validation, manual review freshness, and single-publication locks.

---

## 6. Operational Failure Simulations & Test Evidence

Test Suite: [`tests/test_operations_and_recovery.py`](file:///c:/Users/HP/Downloads/NovaStream/upsc_studio/tests/test_operations_and_recovery.py)  
Total Tests Executed: **12/12 PASSED** in 7.53s.

| Scenario Simulated | Tested Mechanism | Verification Evidence | Result |
| :--- | :--- | :--- | :---: |
| **1. Process Interruption** | Task forced to `RUNNING` (simulated kill/crash); `detect_interrupted_tasks` called. | Task quarantined to `REVIEW_REQUIRED`, error categorized as `FILESYSTEM_FAILURE`, audit event recorded. | **PASSED** |
| **2. Database Lock** | SQLite handler raises `sqlite3.OperationalError: database is locked`. | Classified as `DATABASE_FAILURE`, `is_retryable=True`; retry succeeded on attempt 2. | **PASSED** |
| **3. Network Timeout** | External API raises `TimeoutError`. | Classified as `TRANSIENT_EXTERNAL`, `is_retryable=True`; retried and completed. | **PASSED** |
| **4. Missing Audio** | Pipeline voice stage executed without voice file and with `ai_narration=False`. | Safely transitions to `WAITING_FOR_VOICE`; no crash, no fake speech forged. | **PASSED** |
| **5. FFmpeg Missing** | `find_ffmpeg()` returns `None`. | Rendering raises error; classified as `MISSING_DEPENDENCY`; fails closed without retries. | **PASSED** |
| **6. Disk Space Exhaustion** | Disk space mocked to 0.45 GB (< 1.0 GB limit). | Rendering blocked with "Insufficient disk space"; classified as `FILESYSTEM_FAILURE`. | **PASSED** |
| **7. Duplicate Submission & Upload** | Identical task spec enqueued twice; upload attempted for already published video. | `AgentTaskStore` returns identical `task_id`; `prevent_duplicate_upload` blocks duplicate publication. | **PASSED** |
| **8. Stale Approval Invalidation** | Content changed after project was marked `APPROVED`. | `validate_approval_freshness` detects fingerprint drift and resets project to `NEEDS_REVIEW`. | **PASSED** |
| **9. Failed Dependency Propagation** | Upstream task raises `AcademicQualityError`. | Upstream enters `REVIEW_REQUIRED`; downstream enters `BLOCKED`; state remains clean. | **PASSED** |
| **10. Checkpoint Resumption** | Partial execution; re-running full workflow skips completed tasks. | Stage 1 skipped from cache; Stage 2 executed without duplicating Stage 1. | **PASSED** |
| **11. Operations Observability API** | `GET /api/projects/{id}/operations` invoked. | Returns 7 stages, duration metrics, CPU/RAM/Disk stats, and database integrity. | **PASSED** |
| **12. Workspace Temp File Cleanup** | `POST /api/projects/{id}/cleanup-temp` called on dangling `*.tmp`. | Temp files safely removed and bytes freed reported accurately. | **PASSED** |

---

## 7. Full Regression & Deterministic Evaluation Results

### Combined Test Suite Across Missions 1–5
```powershell
pytest tests/test_operations_and_recovery.py tests/test_voice_multilingual_qa.py tests/test_documentary_visuals.py tests/test_adversarial_research.py tests/test_advanced_teaching_engine.py
```
**Outcome:**
- `test_operations_and_recovery.py`: 12 passed
- `test_voice_multilingual_qa.py`: 10 passed
- `test_documentary_visuals.py`: 7 passed
- `test_adversarial_research.py`: 9 passed
- `test_advanced_teaching_engine.py`: 9 passed
- **Total:** **47 passed** in 51.01s (0 failures, 1 warning)

### Deterministic Agent Evaluation Benchmark
```powershell
python -m upsc_studio.agents.evaluate
```
**Outcome:**
- `case_count`: 12
- `passed`: 12
- `failed`: 0
- **Pass Rate:** **1.0 (100%)**

---

## 8. Known Limitations & Operational Constraints

1. **Integrated GPU Encoders:** On Intel Core i5 with integrated graphics, hardware encoding (`h264_qsv`) requires Intel media driver installation; CPU encoding (`libx264`, `preset="veryfast"`) remains the reliable default.
2. **SQLite Concurrent Writes:** SQLite write concurrency is serial. Background tasks share a single write connection with WAL mode enabled to minimize lock contention.
3. **Semantic Verification Boundary:** The operations engine verifies metadata, fingerprints, and process integrity; semantic truthfulness of academic claims still requires human editorial attestation.
