# UPSC Studio — Architecture & Data Schemas (v1.0)

## 1. System Architecture
Local-first modular Python architecture (`src/upsc_studio/`):
- `core/`: Hardware & tool audit (`hardware.py`), structured logging (`logging_config.py`), config/settings (`config.py`), path safety (`paths.py`).
- `db/`: SQLite persistence with versioned schema (`database.py`) and Pydantic domain schemas (`schemas.py`).
- `projects/`: Project lifecycle, folder scaffolding, backup/restore (`manager.py`).
- `ingestion/`: Multi-format document ingestion (PDF, DOCX, PPTX, XLSX, TXT, MD, Images, URLs, typed text), SHA-256 provenance, duplicate & extraction-failure detection (`ingestor.py`).
- `syllabus/`: Versioned official UPSC syllabus (Prelims GS-I, Prelims CSAT Paper-II, Mains GS-I–IV, Essay, Optional) and explanatory-depth coverage matrix (`engine.py`).
- `research/`: Claim decomposition, source hierarchy, claim-level evidence ledger (`VERIFIED`..`HUMAN_REVIEW_REQUIRED`), conflict & cutoff tracking (`verifier.py`).
- `teaching/`: Fundamentals-to-UPSC teaching outline, Hinglish script with claim links, Prelims/Mains tracks, recording script (`tts_enabled=False` by default), and study pack (`engine.py`).
- `storyboard/`: Scene-by-scene director, teaching purpose, visual category, transitions, animations, and asset requests (`director.py`).
- `graphics/`: Original CPU-safe Pillow/SVG slide, diagram, flowchart, timeline, and data-chart generator + asset provenance & licence ledger (`generator.py`, `rights.py`).
- `audio/`: Own-voice WAV/MP3 ingestion, loudness/peak/clipping/silence inspection, conservative FFmpeg cleanup, and SRT subtitle alignment (`processor.py`).
- `video/`: Resumable scene-wise FFmpeg timeline builder & renderer (`renderer.py`).
- `qa/`: Separate `ACADEMICALLY_REVIEWED`, `RIGHTS_CLEARED`, `VIDEO_TECHNICALLY_APPROVED`, `READY_FOR_PUBLICATION` gates (`auditor.py`).
- `pipeline/`: End-to-end orchestrator supporting `WAITING_FOR_VOICE` pause and resumable stages (`orchestrator.py`).
- `web/`: Local FastAPI dashboard & REST API (`app.py`) where every visible control executes real backend logic.

## 2. Project Directory Layout (`projects/<project_id>/`)
```text
projects/<project_id>/
  project.json
  inputs/originals/       # Immutable original notes & recordings
  inputs/extracted/       # Extraction reports & page text
  research/               # evidence_ledger.json, sources.bib.json, verification_report.md
  syllabus/               # chapter_map.json, coverage_matrix.json
  teaching/               # script_hinglish.md, recording_script.md, study_notes.md, question_bank.json
  storyboard/             # storyboard.json, graphics_spec.json, transition_plan.json
  assets/generated/       # Original PNG/SVG diagrams, charts, slides
  assets/manifests/       # asset_rights.json
  audio/processed/        # Conservative cleaned voice + audio_qa.json
  subtitles/              # subtitles.srt, transcript.json
  render/scenes/          # Cached per-scene MP4 segments
  render/final/           # Final assembled MP4 + render_manifest.json
  qa/                     # academic_qa.json, rights_qa.json, media_qa.json, release_readiness.md
  logs/                   # Project execution logs
```

## 3. Core Database Tables (SQLite)
- `projects` (`id`, `name`, `chapter_title`, `exam_cycle`, `cutoff_date`, `target_duration_min`, `status`, `created_at`, `updated_at`)
- `source_documents` (`id`, `project_id`, `filename`, `file_type`, `sha256`, `original_path`, `page_count`, `extraction_status`, `diagnostics_json`, `created_at`)
- `syllabus_items` (`id`, `version`, `stage`, `paper`, `topic`, `subtopic`, `keywords_json`, `source_ref`)
- `coverage_ledger` (`id`, `project_id`, `syllabus_item_id`, `status`, `reason`, `note_refs_json`, `script_section_id`, `scene_id`, `study_ref`)
- `sources` (`id`, `project_id`, `title`, `publisher`, `url`, `pub_date`, `access_date`, `source_tier`, `notes`)
- `claims` (`id`, `project_id`, `statement`, `chapter_section`, `scene_id`, `source_id`, `page_or_section`, `ref_period`, `status`, `verification_notes`)
- `assets` (`id`, `project_id`, `asset_type`, `file_path`, `sha256`, `creator`, `origin_url`, `licence`, `attribution`, `rights_status`, `retrieved_at`)
- `render_jobs` (`id`, `project_id`, `scene_id`, `status`, `output_path`, `input_hash`, `command`, `error_message`, `updated_at`)
- `qa_gates` (`id`, `project_id`, `gate_name`, `status`, `blocking_issues_json`, `checked_at`, `approved_by`)
- `backups` (`id`, `project_id`, `backup_path`, `created_at`, `notes`)
