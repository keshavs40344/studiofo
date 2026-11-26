# Implementation Roadmap — UPSC Studio

1. **Completed Foundation & Production Core (Phases 1–12 baseline):** Hardware audit, SQLite persistence, ingestion, syllabus, evidence, teaching, storyboard, graphics, own-voice audio, FFmpeg video rendering, QA gates, FastAPI UI, 10-chapter benchmarks.
2. **Current Hardening Pass:**
   - Centralize `FREE_FIRST / LOCAL_FIRST / PAID_SERVICES_ENABLED=False` budget policy guard (`core/policy.py`).
   - Add explicit stage-level `job_manifest.json` checkpointing & temp-file cleanup (`pipeline/job_manifest.py`).
   - Add script-to-transcript missing/extra sentence comparison (`audio/processor.py`).
   - Register `Blender`, `Audacity`, and `whisper.cpp` in `integrations/registry.py`.
3. **Optional Future Enhancements (When User Installs Tools):**
   - Install `Tesseract` for scanned PDF OCR.
   - Install `whisper.cpp` or `faster-whisper` and benchmark Hindi/Hinglish WER on user's own voice.
   - Install `QGIS` / `Blender` / `Manim` in isolated environments if advanced GIS/3D renders are needed.
