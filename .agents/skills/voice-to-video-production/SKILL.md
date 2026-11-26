---
name: voice-to-video-production
description: Processes the user's own narration, aligns transcript and subtitles to storyboard scenes, creates a resumable media timeline and renders a complete educational video with FFmpeg or verified local tools.
---
# Voice-to-Video Production

1. Require the user's own voice recording as narration. If it is absent, create a section-wise recording request and pause only the voice-dependent stage.
2. Preserve raw voice files unchanged and create processed copies.
3. Validate file readability, channels, sample rate, clipping, noise, dropouts and silence.
4. Apply conservative cleanup; preserve natural voice quality. Never clone, synthesise or replace the voice by default.
5. Transcribe speech using an available local or approved service. Correct names, Hindi-English terms and technical vocabulary against the approved script; flag mismatches instead of silently rewriting meaning.
6. Align transcript segments to storyboard sections and generate timed subtitles in Hindi/English/Hinglish as appropriate.
7. Build a structured, editable timeline. Use source-to-scene links, asset licences, narration segments, titles, graphics, transitions, music and sound effects.
8. Use only rights-cleared media. Prefer original graphics when no safe asset is available.
9. Render scene-wise or section-wise for recovery. Cache completed segments and re-render only changed/failed scenes.
10. Use CPU-safe settings based on actual hardware detection. Start with proxies and conservative preview quality. Do not assume hardware encoding exists.
11. Mix narration clearly above licensed music/ambience. Measure output loudness, peaks and clipping rather than guessing.
12. Validate final file with actual media probes and playback/sample inspection. Verify resolution, frame rate, duration, audio stream, subtitles, missing media, black frames and render completion.
13. Save exact commands, logs, source manifest and render settings.

Deliverables: `transcript.json`, `subtitles.srt`, `timeline.json`, `render_manifest.json`, final video and `render_report.md`.
