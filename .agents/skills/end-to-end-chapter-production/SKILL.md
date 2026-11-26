---
name: end-to-end-chapter-production
description: Orchestrates the complete UPSC Studio chapter workflow from topic and notes to evidence-backed lesson, user's own voice, automatic visual production, final video, study pack and release-readiness report.
---
# End-to-End UPSC Chapter Production

Use the focused skills in this order:
1. upsc-chapter-planner
2. research-verification
3. teaching-script-writer
4. visual-storyboard-director
5. voice-to-video-production
6. academic-video-qa

## Inputs
- Required: chapter/topic OR uploaded notes that identify the chapter.
- Optional: the user's additional notes, preferred duration, target exam cycle and style preferences.
- Required for narrated final render: the user's own voice recording.
- No AI narration/voice clone by default.

## Orchestration protocol
1. Create a new versioned project and record inputs.
2. Inspect uploaded files and produce an extraction quality report.
3. Map the topic to the official syllabus and generate the coverage matrix.
4. Research missing/current information and verify claims.
5. Build the teaching outline and script from approved evidence.
6. Generate study materials from the same evidence base.
7. Generate scene-level storyboard and asset/graphics requests.
8. Acquire only permitted assets; generate original graphics when practical.
9. Create the user's section-wise voice recording instructions. If voice is absent, finish all voice-independent preparation and wait in WAITING_FOR_VOICE.
10. Once voice is supplied, process, transcribe, align and build subtitles.
11. Assemble and render the complete timeline with resumable scene jobs.
12. Run academic, rights, teaching, visual, audio and export QA.
13. Produce the final video and complete study pack only when required gates pass. If not, produce a release candidate with explicit blockers.

## Automation policy
Automate every repeatable step that can be executed with verified installed tools and permitted services. Do not ask the user to manually research, script, design, animate, edit or subtitle. Ask only for genuinely necessary inputs such as the chapter/topic, inaccessible source files, user's own voice recording, or a permission/cost approval required by a connected external service.

## Failure handling
- Continue independent stages when one optional service fails.
- Save intermediate artefacts and resume from last successful stage.
- Never substitute fake research, fake assets or synthetic narration.
- When a dependency is unavailable, use a documented local fallback where possible; otherwise identify the exact blocker.
- Never claim the video is complete if it was not actually rendered and inspected.

## Completion report
Include chapter coverage, evidence status, unresolved claims, asset rights, duration, voice/transcript status, scene count, outputs, exact QA results and release status.
