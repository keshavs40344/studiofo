# Development Setup

## Prerequisites

- Python ≥ 3.11 (tested with 3.14)
- Windows 10/11
- Git

## Installation

```bash
git clone https://github.com/keshavs40344/studiofo.git
cd studiofo

python -m venv .venv
.venv\Scripts\activate

pip install -e ".[docs,dev]"
```

## Running the app

```bash
python -m upsc_studio
```

The FastAPI dashboard starts at `http://127.0.0.1:8000`.

## Running tests

```bash
python -m pytest -v
```

Expected: 25 tests passing across 8 test files.

## Optional: Piper TTS

Piper requires an isolated virtual environment to avoid dependency conflicts:

```bash
python -m venv .venv_tts
.venv_tts\Scripts\activate
pip install piper-tts
```

Download the Hindi voice model `hi_IN-pratham-medium.onnx` from [Piper voices](https://github.com/rhasspy/piper/releases) and place it in `data/tts_models/piper/`.

## Environment variables

Copy `.env.example` to `.env` and fill in any optional API keys. The application runs fully offline without them.

## Project conventions

- Source code lives in `src/upsc_studio/`.
- Tests live in `tests/`.
- Generated project outputs go to `projects/` (gitignored).
- TTS model binaries go to `data/tts_models/` (gitignored).
