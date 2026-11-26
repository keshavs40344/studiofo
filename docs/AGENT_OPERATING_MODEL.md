# UPSC Studio — Agent Operating Model

> **Note:** This configuration does not fine-tune or retrain the underlying Gemini model. It provides persistent workspace rules (`AGENTS.md`) and modular task skills (`.agents/skills/*/SKILL.md`) so the agent operates consistently with UPSC Studio's engineering and academic standards.

## 1. Persistent Rules (`AGENTS.md`)
Located at the workspace root (`C:\Users\HP\Downloads\NovaStream\AGENTS.md`) and project root (`upsc_studio/AGENTS.md`). Key non-negotiable constraints:
- **Own-Voice Default:** User's own recorded narration is the default; TTS and voice cloning remain disabled unless explicitly enabled by the user. If voice is absent, complete all voice-independent stages and set project state to `WAITING_FOR_VOICE`.
- **Evidence & Truthfulness:** Never fabricate sources, citations, PYQs, statistics, quotes, or test results. Separate `VERIFIED`, `PARTIALLY_VERIFIED`, `CONFLICTING`, `OUTDATED`, `UNSUPPORTED`, and `HUMAN_REVIEW_REQUIRED`.
- **Syllabus Separation:** Maintain versioned official UPSC syllabus; keep Prelims GS-I, Prelims CSAT Paper-II, Mains GS-I–IV, Essay, and Optional strictly distinct.
- **Asset Provenance & Rights:** Never include `UNVERIFIED` external assets in final exports; prefer original vector/data graphics when licensed footage is unavailable.
- **Hardware-Aware Execution:** Target Windows laptop (`11th Gen Intel i5-1135G7`, `15.69 GB RAM`, integrated `Intel Iris Xe Graphics`, no dedicated GPU) with CPU-safe defaults (1080p/30fps, scene-wise rendering, capped concurrency, resumable jobs).
- **Separate QA Gates:** `ACADEMICALLY_REVIEWED`, `RIGHTS_CLEARED`, `VIDEO_TECHNICALLY_APPROVED`, and `READY_FOR_PUBLICATION`.

## 2. Skill Catalogue (`.agents/skills/`)

| Skill | Purpose | Primary Deliverables |
|---|---|---|
| `end-to-end-chapter-production` | Orchestrates full chapter pipeline from topic/notes to final video & study pack | Full project state & completion report |
| `upsc-chapter-planner` | Maps topic/notes to official syllabus, cross-paper links, and coverage matrix | `chapter_map.json`, `coverage_matrix.json`, `learning_objectives.md`, `chapter_outline.md` |
| `research-verification` | Researches official/reputable sources and verifies atomic factual claims | `evidence_ledger.json`, `sources.bib.json`, `verification_report.md`, `unresolved_claims.md` |
| `teaching-script-writer` | Writes Hinglish teaching script, Prelims/Mains tracks, recording script & study notes | `teaching_outline.md`, `script_hinglish.md`, `prelims_track.md`, `mains_track.md`, `study_notes.md`, `revision_sheet.md`, `question_bank.json`, `recording_script.md` |
| `visual-storyboard-director` | Converts script into scene-level storyboard, graphics specs, transitions & asset requests | `storyboard.json`, `visual_asset_requests.json`, `graphics_spec.json`, `transition_plan.json`, `visual_qa_checklist.md` |
| `voice-to-video-production` | Processes own voice, transcribes/aligns subtitles, builds timeline & renders via FFmpeg | `transcript.json`, `subtitles.srt`, `timeline.json`, `render_manifest.json`, final MP4, `render_report.md` |
| `academic-video-qa` | Audits academic completeness, rights clearance, media/audio/export quality | `academic_qa.json`, `rights_qa.json`, `media_qa.json`, `release_readiness.md` |

## 3. Skill Selection & Precedence
1. Always follow root `AGENTS.md` as the baseline invariant across all tasks.
2. For full chapter production, invoke `end-to-end-chapter-production`, which sequences the 6 specialist skills in order.
3. For targeted operations (e.g., auditing a rendered video or verifying claims), invoke the corresponding specialist skill directly.
