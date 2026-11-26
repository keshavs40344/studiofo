# Repository Audit — UPSC Studio

**Audit Date:** 2026-11-26  
**Repository Root:** `C:\Users\HP\Downloads\NovaStream\upsc_studio`

## 1. Existing Structure & Entry Points
- **Package:** `src/upsc_studio/` (`__main__.py` launches FastAPI + Uvicorn on `127.0.0.1:8765`).
- **Persistence:** SQLite database (`data/upsc_studio.db`) + per-project directories (`projects/<slug>_<id>/`).
- **Core Modules:** `core/` (hardware, paths, logging), `db/` (SQLite schema + Pydantic schemas), `projects/` (lifecycle, backup/restore), `ingestion/` (PDF/DOCX/PPTX/XLSX/TXT/MD/Image), `syllabus/` (versioned UPSC syllabus), `research/` (claim-level evidence ledger), `academic/` (8 GS specialist profiles, PYQ engine, Mains directive analyzer), `teaching/` (Hinglish script, study pack, duration planner), `storyboard/` (scene specs, adaptive visuals), `graphics/` (Pillow slides, flowcharts, split-screen, data charts, thumbnail, rights ledger), `integrations/` (tool registry, Manim/FFmpeg animation engine, QGIS/map fallback, OTIO exporter), `audio/` (own-voice cleanup, `loudnorm`, section-wise retakes, SRT subtitles), `video/` (scene-wise cached FFmpeg renderer, `xfade` transitions, chapter metadata), `qa/` (4 release gates, 10-gate audit, `blackdetect` completeness audit, 10-chapter benchmark auditor), `pipeline/` (end-to-end orchestrator), `web/` (FastAPI dashboard).

## 2. Gaps Identified During Audit
1. Explicit `FREE_FIRST / LOCAL_FIRST / PAID_SERVICES_ENABLED=False` budget & cloud policy guard module was not yet centralized.
2. Stage-level `job_manifest.json` checkpointing for skipping completed research/teaching stages on render retry was implicit rather than explicit.
3. Script-to-transcript missing/extra sentence comparison helper was not yet exposed in `VoiceAudioProcessor`.
4. `Blender`, `Audacity`, and `whisper.cpp` were not yet listed in `integrations/registry.py`.
5. `tesseract` OCR, `qgis`, `blender`, `whisper.cpp`, and `audacity` are not installed on this Windows machine; local fallbacks are used.
