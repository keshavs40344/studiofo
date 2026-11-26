# UPSC Studio — Baseline Audit Report

**Audit Date:** 2026-11-26  
**Workspace Inspected:** `C:\Users\HP\Downloads\NovaStream`  
**Project Root Created:** `C:\Users\HP\Downloads\NovaStream\upsc_studio`

## 1. Existing Repository & Features
- **Existing Codebase:** None. `C:\Users\HP\Downloads\NovaStream` contained only 20 unrelated IIT Madras BS Qualifier media files (`.mp4`, `.png`, `.temp.mp4`, `.webp`) and the `Antigravity_UPSC_Training` pack (`AGENTS.md`, `START_HERE.md`, `BOOTSTRAP_PROMPT.md`, `.agents/skills/*`).
- **Working Features at Baseline:** 0 application modules, 0 database files, 0 tests.
- **Incomplete / Missing Features:** All 12 phases (Foundation, Ingestion, Syllabus Engine, Research/Evidence, Teaching/Script, Storyboard, Graphics/Assets, Voice/Subtitles, Timeline/Rendering, QA Gates, Learning Package, E2E Integration).

## 2. Environment & Hardware Audit (Verified)
| Item | Measured Fact |
|---|---|
| **OS** | Windows |
| **CPU** | 11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz (4 cores, 8 logical processors) |
| **RAM** | 15.69 GB |
| **GPU** | Intel(R) Iris(R) Xe Graphics (integrated; no dedicated GPU) |
| **Disk (`C:`)** | 104.04 GB free / 285.43 GB used |
| **Python** | Python 3.14.6 (`C:\Python314\python.exe`) |
| **FFmpeg** | `ffmpeg-win-x86_64-v7.1.exe` bundled via `imageio-ffmpeg 0.6.0` (not on system `PATH`) |
| **Git / Node** | `git` (`C:\Program Files\Git\cmd\git.exe`), `node`, `npm` installed |
| **Optional External Tools Not Found** | `ffmpeg` (on PATH), `ffprobe`, `tesseract`, `inkscape`, `qgis`, `kdenlive` |

## 3. Pre-installed Python Libraries Available
`fastapi 0.141.1`, `uvicorn 0.49.0`, `pydantic 2.13.5`, `pydantic-settings 2.15.0`, `SQLAlchemy 2.0.52`, `pillow 12.2.0`, `numpy 2.5.0`, `pandas 3.0.4`, `altair 6.2.2`, `imageio-ffmpeg 0.6.0`, `pytest 9.1.1`, `httpx 0.28.1`, `requests 2.34.2`, `beautifulsoup4 4.15.0`, `psutil 7.2.2`, `Jinja2 3.1.6`.

## 4. Risks & Mitigations
- **Hardware / Performance Risk:** 15.69 GB RAM + integrated GPU means simultaneous heavy FFmpeg/Whisper jobs can cause memory pressure or thermal throttling.
  - *Mitigation:* Use `libx264` CPU-safe presets, 1080p/30fps (or 720p proxy preview), scene-wise rendering with segment caching, max 1–2 concurrent render jobs, and pre-render free disk space checks.
- **Missing Document Extractors / OCR:** `tesseract` is not installed; `pypdf` / `python-docx` / `python-pptx` / `openpyxl` should be checked/installed as needed, with explicit `OCR_UNAVAILABLE` diagnostics when scanned PDFs/images cannot be OCR'd.
- **Data-Loss & Security Risks:** Original user notes and raw voice recordings must never be overwritten; API keys must never be hardcoded; external assets without verified licences must be marked `UNVERIFIED` and blocked from final export.

## 5. Baseline Test Results
- **Tests Available:** None at baseline.

## 6. Implementation Sequence (Milestones)
1. **Milestone 1 (Phases 1–3):** Project foundation (SQLite DB, project manager, hardware detector, logging, backup/restore), document ingestion (TXT/MD/PDF/DOCX/Images with hash & page refs), versioned UPSC syllabus & chapter coverage matrix.
2. **Milestone 2 (Phases 4–5):** Research & claim-level evidence ledger (`VERIFIED`..`HUMAN_REVIEW_REQUIRED`), Hinglish teaching & script engine, Prelims/Mains separation, recording script & study materials.
3. **Milestone 3 (Phases 6–9):** Storyboard director, original Pillow/SVG graphics & chart generator, asset rights ledger, own-voice WAV/audio processor & subtitle aligner, FFmpeg scene-wise timeline renderer.
4. **Milestone 4 (Phases 10–12):** Academic/Rights/Media/Export QA gates, local FastAPI desktop dashboard UI, and full end-to-end integration test with real rendered MP4 inspection.
