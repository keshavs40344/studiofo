# UPSC Studio

Local-first autonomous UPSC General Studies research, teaching, and video production system.

## What it does

UPSC Studio automates the full educational documentary production workflow:

1. **Document ingestion** — PDF, DOCX, PPTX, XLSX, TXT, Markdown with SHA-256 provenance and duplicate detection.
2. **Syllabus intelligence** — Versioned official UPSC syllabus mapping (Prelims GS-I, CSAT Paper-II, Mains GS-I–IV, Essay, Optional) with explanatory-depth coverage matrix.
3. **Academic research & verification** — Claim-level evidence ledger with statuses (`VERIFIED`, `PARTIALLY_VERIFIED`, `CONFLICTING`, `OUTDATED`, `UNSUPPORTED`, `HUMAN_REVIEW_REQUIRED`), source hierarchy, and URL reachability checks.
4. **Teaching engine** — Hinglish fundamentals-to-UPSC script, Prelims/Mains learning tracks, recording script, study notes, revision sheets, definitions, Mermaid mind maps, practice MCQs, and Mains directive frameworks.
5. **Storyboard & visuals** — Scene-by-scene documentary direction with Pillow/FFmpeg 1080p slides, process animations, institutional maps, data charts, split-screen comparisons, and original graphics.
6. **Voice processing** — Own-voice WAV/MP3 ingestion, loudness/peak/clipping/silence analysis, conservative FFmpeg cleanup, section-wise retakes, and SRT subtitle alignment.
7. **Video rendering** — Resumable scene-wise FFmpeg timeline builder, OTIO Timeline export, `blackdetect` continuity check, and final MP4 assembly.
8. **Quality assurance** — 10-gate QA system with separate `ACADEMICALLY_REVIEWED`, `RIGHTS_CLEARED`, `VIDEO_TECHNICALLY_APPROVED`, and `READY_FOR_PUBLICATION` gates.
9. **Publishing** — 1280×720 thumbnail, editorial metadata optimizer, and YouTube publisher (pending OAuth).

## User workflow

Your personal contribution is limited to:

1. Select a UPSC GS chapter/topic (or upload notes).
2. Upload your own recorded narration.

Everything else is automated.

## Tech stack

| Component | Technology |
|---|---|
| Language | Python ≥ 3.11 |
| Backend | FastAPI + Uvicorn |
| Database | SQLite |
| Data models | Pydantic v2 |
| Image generation | Pillow |
| Video encoding | FFmpeg (via `imageio-ffmpeg`) |
| TTS (optional) | Piper (Hindi, isolated venv) |
| Timeline export | OpenTimelineIO |
| Audio processing | FFmpeg `loudnorm`, `silencedetect`, `blackdetect` |

## Quick start

```bash
# Clone the repository
git clone https://github.com/keshavs40344/studiofo.git
cd studiofo

# Create a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

# Install in editable mode
pip install -e ".[docs,dev]"

# Run the development server
python -m upsc_studio
# → http://127.0.0.1:8000
```

## Running tests

```bash
python -m pytest -v
```

25 tests covering foundation, ingestion, syllabus, academic intelligence, production pipeline, ecosystem adapters, and 10-chapter golden benchmark.

## Project structure

```
upsc_studio/
├── src/upsc_studio/        # Main source package
│   ├── core/               # Hardware audit, paths, logging, policy
│   ├── db/                 # SQLite database, Pydantic schemas
│   ├── projects/           # Project lifecycle management
│   ├── ingestion/          # Multi-format document ingestion
│   ├── syllabus/           # Versioned UPSC syllabus engine
│   ├── research/           # Claim-level evidence verification
│   ├── academic/           # GS specialists, PYQ engine, Mains analyzer
│   ├── teaching/           # Script engine, duration planner
│   ├── storyboard/         # Visual direction, adaptive visuals
│   ├── graphics/           # Image generation, rights management
│   ├── integrations/       # Manim, QGIS, OTIO, Altair adapters
│   ├── audio/              # Voice processing, section recordings
│   ├── video/              # FFmpeg scene renderer
│   ├── qa/                 # 10-gate quality assurance
│   ├── pipeline/           # End-to-end orchestrator
│   ├── tts/                # Piper TTS adapter, pronunciation
│   ├── agents/             # Multi-agent supervisor, contracts
│   ├── publishing/         # YouTube publisher, editorial optimizer
│   └── web/                # FastAPI dashboard
├── data/                   # Syllabus JSON, GS profiles, PYQ bank
├── tests/                  # Automated test suite (25 tests)
├── scripts/                # Demo and utility scripts
├── docs/                   # Architecture, roadmap, audit docs
└── .agents/skills/         # Antigravity agent skill definitions
```

## Documentation

- [Architecture & Schemas](docs/ARCHITECTURE_AND_SCHEMAS.md)
- [Current Capabilities](docs/CURRENT_CAPABILITIES.md)
- [Implementation Roadmap](docs/IMPLEMENTATION_ROADMAP.md)
- [Dependency & Licence Register](docs/DEPENDENCY_AND_LICENCE_REGISTER.md)
- [Upstream Evaluation](docs/UPSTREAM_EVALUATION.md)
- [Ecosystem Discovery](docs/ECOSYSTEM_DISCOVERY_AND_SHORTLIST.md)
- [Agent Operating Model](docs/AGENT_OPERATING_MODEL.md)

## Hardware requirements

- Windows 10/11 (primary target)
- 16 GB RAM
- Intel Core i5 or equivalent
- SSD with ≥ 10 GB free
- FFmpeg (bundled via `imageio-ffmpeg`)
- No dedicated GPU required (CPU-safe defaults)

## Licence

MIT
