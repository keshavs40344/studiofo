# Advanced Voice, Audio and Multilingual Quality System — Verification Report

## Mission Overview
This report documents the architectural design, implementation, and empirical testing of the **Advanced Voice, Audio and Multilingual Quality System** for UPSC Studio (`studiofo`), implemented on working branch `phase17/recovery-runtime-integration` (associated with PR #2).

The core mission is to establish an authentic, high-fidelity voice and audio pipeline where the master production language is **natural Hinglish**, user voice recordings are strictly preserved without synthetic impersonation, pronunciation intelligence handles complex bilingual academic terminology, subtitles follow professional readability and drift constraints, and multilingual dubbing strictly progresses through an explicit 9-stage lifecycle.

---

## 1. Own-Voice Audio Inspection & Normalization

Implemented in `src/upsc_studio/audio/quality.py` (`AudioQualityInspector`) and `src/upsc_studio/audio/processor.py` (`VoiceAudioProcessor`):
- **User Voice Integrity**:
  - The user's original recorded voice is preserved verbatim in `audio/raw/`.
  - The system explicitly records `tts_used: false` and `voice_cloning_used: false`.
  - Synthetic speech is never presented as the user's authentic recording.
- **Audio Quality Diagnostics**:
  - **Sample Rate Validation**: Enforces broadcast minimum (44.1 kHz or 48 kHz).
  - **Peak & Clipping Detection**: Scans 16-bit PCM waveform samples against a `0.985` amplitude threshold (approx -0.1 dBFS); flags excessive clipped samples.
  - **Prolonged Silence Detection**: Analyzes 100ms sliding windows for energy below -36 dBFS; flags dead air runs exceeding the `3.0s` limit.
  - **Noise Floor & SNR Estimation**: Measures average amplitude during silent pauses; flags high ambient noise if noise floor exceeds -35 dBFS.
- **Conservative Normalization**:
  - Highpass filter (80 Hz) eliminates low-frequency desk vibrations, HVAC rumble, and mic handling thumps.
  - EBU R128 loudness normalization targets integrated loudness `I = -16.0 LUFS` with a true peak ceiling `TP = -1.5 dBFS`, achieving consistent broadcast loudness without dynamic distortion.
- **Section-Wise Retakes & Continuity**:
  - `SectionVoiceManager` tracks section recordings independently, allowing retakes of single flawed sections without re-recording the entire chapter.
  - Measures pace ratio against expected script reading duration (flagging omissions or extreme dragging).

---

## 2. Advanced Pronunciation Intelligence

Implemented in `src/upsc_studio/tts/pronunciation_lexicon.py` (`AdvancedPronunciationLexicon`):
- **Core Lexicon Coverage**:
  - **Abbreviations & Acronyms**: `UPSC` ("यू पी एस सी"), `CSAT` ("सी सैट"), `NITI Aayog` ("नीति आयोग"), `RBI`, `CAG`, `ECI`, `NHRC`, `MoSPI`, `SEBI`.
  - **Constitutional & Legal Terms**: `Habeas Corpus` ("हेबियस कॉर्पस"), `Mandamus` ("मैंडेमस"), `Certiorari` ("सर्शियोरारी"), `Quo Warranto` ("को वारंटो"), `Prohibition` ("प्रोहिबिशन"), `Suo Motu` ("सुओ मोटो"), `Ultra Vires` ("अल्ट्रा वायरस"), `Ratio Decidendi`, `Obiter Dicta`, `Amicus Curiae`.
  - **Landmark Case Precedents**: `K.S. Puttaswamy` ("के एस पुट्टास्वामी"), `Kihoto Hollohan` ("किहोतो होलोहन"), `Kesavananda Bharati`, `Maneka Gandhi`, `Minerva Mills`, `Indra Sawhney`.
  - **Historical Names**: `Chandragupta` ("चन्द्रगुप्त"), `Ashoka` ("अशोक"), `Akbar` ("अकबर"), `B.R. Ambedkar` ("बी आर अंबेडकर"), `Bal Gangadhar Tilak`, `Dadabhai Naoroji`, `Subhas Chandra Bose`.
  - **Geographical Names**: `Tsangpo` ("त्सांगपो"), `Lakshadweep` ("लक्षद्वीप"), `Western Ghats` ("वेस्टर्न घाट्स"), `Coromandel`, `Sundarbans`, `Deccan Plateau`, `Siachen`.
  - **Scientific & Economic Terms**: `Photosynthesis` ("फोटोसिंथेसिस"), `Chlorophyll` ("क्लोरोफिल"), `Photovoltaic`, `Troposphere`, `Repo Rate`, `Fiscal Deficit`.
  - **Numbers, Dates, and Units**: Conversions for landmark years (`1947` -> "उन्नीस सौ सैंतालीस", `1976` -> "उन्नीस सौ छिहत्तर"), constitutional amendment numbers (`42nd` -> "बयालीसवां", `44th` -> "चौवालीसवां"), `%` -> "प्रतिशत", and `GW` -> "गीगावाट".
- **Project-Level Pronunciation Overrides**:
  - Persists and loads overrides from `audio/tts/pronunciation_overrides.json`.
  - Evaluates longest matches first to prevent partial substrings from corrupting terminology.
  - **Strict Semantic Rule**: Pronunciation adjustments alter phonetic representations for audio engines only; they never modify underlying script meaning or factual assertions.

---

## 3. Broadcast Subtitle Alignment & Readability

Implemented in `src/upsc_studio/audio/subtitles.py` (`SubtitleEngine`):
- **Readability & Line-Splitting**:
  - Subtitle cues are clamped to **maximum 42 characters per line** and **maximum 2 lines per cue**.
  - Long compound sentences are broken into natural phrasing at clause and punctuation boundaries.
- **Pacing & Timing Standards**:
  - Minimum on-screen cue duration: **1.0 second**.
  - Maximum on-screen cue duration: **7.0 seconds**.
  - Reading speed limit: **<= 21 characters/second** for comfortable viewer comprehension.
  - Sequential cues maintain a **50ms buffer gap** to prevent visual bleeding.
- **Dual Format Support**:
  - Outputs standard SubRip (`.srt`) and WebVTT (`.vtt`) files.
- **Quality Inspection**:
  - `SubtitleEngine.inspect_cues_quality` automatically detects overlapping cues, negative durations, or excessive reading speeds.
- **Limitation Notice**:
  - In the absence of an installed local acoustic alignment model (e.g. Whisper / gentle), sentence-level proportional temporal distribution is used and explicitly reported.

---

## 4. Nine-Stage Multilingual Lifecycle

Implemented in `src/upsc_studio/languages/lifecycle.py` (`MultilingualLifecycleManager`):
To prevent superficial claims of completed multilingual dubbing, every supported language track progresses through 9 distinct, verifiable stages:

1. `CATALOGUE_AVAILABLE`: Language cataloged in the 16 supported languages.
2. `TRANSLATION_PROVIDER_AVAILABLE`: Machine translation provider (LibreTranslate / Argos Translate) is available.
3. `TRANSLATION_COMPLETED`: Translated target text generated.
4. `HUMAN_TRANSLATION_QA_COMPLETED`: Named human translator has reviewed and signed off on accuracy.
5. `TARGET_VOICE_INSTALLED`: Licensed local voice model (e.g. Piper ONNX) installed.
6. `VOICE_LICENSING_VERIFIED`: Commercial/educational voice license verified and recorded in rights ledger.
7. `DUBBING_GENERATED`: Target language audio synthesized and synchronized.
8. `AUDIO_QA_COMPLETED`: Target audio has passed loudness (-16 LUFS), clipping, and silence QA checks.
9. `FINAL_LANGUAGE_TRACK_APPROVED`: Release approval granted.

> [!IMPORTANT]
> **Strict Operational Rule**: A catalogue entry is NEVER treated as a completed or release-ready language. Skipping gates (e.g. jumping directly to `FINAL_LANGUAGE_TRACK_APPROVED` without human translation QA or audio QA) raises a hard validation error.

---

## 5. Verification Test Suite Results

Executed via `pytest tests/test_voice_multilingual_qa.py -v`:

| Test Case | Adversarial Vector / Condition | Result | Status |
|---|---|---|---|
| `test_corrupt_audio_rejection` | Truncated bytes / invalid RIFF header | `FAILED` status, corrupt header issue logged | **PASSED** |
| `test_incorrect_sample_rate_detection` | 16 kHz audio fixture (< 44.1 kHz standard) | Sub-standard rate flagged | **PASSED** |
| `test_clipping_detection` | Synthetic square wave hitting 1.0 ceiling | Clipping samples detected, clipping issue logged | **PASSED** |
| `test_excessive_silence_detection` | 3.5s silent gap in 4.5s recording | Excessive dead air detected (> 3.0s limit) | **PASSED** |
| `test_clean_audio_inspection_passes` | 44.1 kHz clean sine speech proxy | `PASSED` status, 0 issues logged | **PASSED** |
| `test_subtitle_line_splitting_and_drift_detection` | 130-char legal sentence + overlapping cues | Lines split <= 42 chars; overlap detected | **PASSED** |
| `test_advanced_pronunciation_lexicon_and_project_overrides` | Case names, Latin writs, year 1947, project override | Normalized correctly; override persisted | **PASSED** |
| `test_missing_translation_provider_handling` | Translation service called without active server | Raises `TranslationUnavailable` with guidance | **PASSED** |
| `test_missing_voice_model_handling` | Synthesize scenes with missing Piper ONNX model | Fails closed (`FileNotFoundError`/`ValueError`) | **PASSED** |
| `test_multilingual_9_stage_lifecycle_enforcement` | Attempting direct approval without QA gates | Blocked by prerequisite validation; full sequence passes | **PASSED** |

**Test Result: 10/10 PASSED in 4.80 seconds.**

---

## 6. External Resources and Dependencies Status

| Component | Current State | External Resource Required for Production |
|---|---|---|
| Hinglish Master Voice | **Functional** | User's own recording via microphone or line-in |
| Local Hindi TTS Fallback | **Functional** | Isolated Piper runtime (`.venv_tts`) + `hi_IN-pratham-medium.onnx` (pre-installed in workspace) |
| Audio Diagnostics & Normalization | **Functional** | Bundled FFmpeg (`ffmpeg-win-x86_64-v7.1.exe`) |
| Subtitle Engine (SRT/VTT) | **Functional** | Pure Python implementation (no external dependencies) |
| Multilingual Machine Translation | **Offline Framework Ready** | Local LibreTranslate server on `127.0.0.1:5000` or `argostranslate` packages |
| Regional Indian Language Dubbing | **Lifecycle Framework Ready** | Regional Piper ONNX models (e.g. Tamil, Bengali, Telugu) to be placed in `data/tts_models/piper/` |
