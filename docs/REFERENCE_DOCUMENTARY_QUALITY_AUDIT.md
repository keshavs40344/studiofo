# Documentary Reference Benchmark and Production Acceptance Audit

**Repository:** `keshavs40344/studiofo`  
**Audit branch:** `audit/documentary-reference-quality-baseline`  
**Audit baseline:** `phase17/recovery-runtime-integration` at `59fb1dbc77c0d0bfc76d3e9ac2736375d870e944`  
**Purpose:** Translate the creator's reference videos and the repository's written production requirements into measurable, evidence-backed acceptance criteria.

## 1. Scope and evidence limits

This is a code-and-repository audit, not a claim that all eight YouTube videos have been watched frame-by-frame. The YouTube players could not be fetched reliably in this audit environment. The eight supplied links are preserved below as the reference set; direct playback review, title verification, scene/timecode notes, and per-reference shot analysis remain pending.

1. https://youtu.be/MkrfVSVO5m0
2. https://youtu.be/KyHpwgkeVx0
3. https://youtu.be/GC7w_HFW64I
4. https://youtu.be/ODWKrhs_5xs
5. https://youtu.be/Ey_W4eaA8dQ
6. https://youtu.be/O3m3P6ERTwE
7. https://youtu.be/32XmLQxwhlQ
8. https://youtu.be/fhQitKgjxO4

Reference videos are quality benchmarks, not assets to copy or reuse. Their footage, music, graphics, scripts, and other protected material must not be copied. The production system must create original explanatory work or use assets with verified permitted-use rights.

Repository evidence inspected:
- `AGENTS.md` — persistent production contract and engineering constraints.
- `README.md` and `docs/CURRENT_CAPABILITIES.md` — declared stack and capabilities.
- `src/upsc_studio/storyboard/director.py`
- `src/upsc_studio/pipeline/staged.py`
- `src/upsc_studio/graphics/documentary_animations.py`
- `src/upsc_studio/video/renderer.py`
- `src/upsc_studio/qa/documentary_quality_gate.py` on `feature/universal-documentary-editorial-standard`.
- GitHub Actions run `46169624332` on PR #2 / commit `59fb1db`.

A file existing in a repository is not proof that it is wired into the active end-to-end pipeline. A passing unit test is not proof of visual quality, academic completeness, voice quality, or release readiness.

## 2. Verified baseline findings

### 2.1 Renderer and visual-generation findings

| Finding | Evidence in code | Effect / risk |
|---|---|---|
| The visual animation suite synthesizes still Pillow frames and encodes them as MP4 segments. | `graphics/documentary_animations.py` | Step-reveal animation is possible, but this is not equivalent to continuous camera animation, 3D reconstruction, or real documentary footage. |
| The map explanation renderer draws labelled rectangular rows/cards. It does not draw geographic geometry, a basemap, coordinate system, boundaries, or routes. | `render_map_explanation` | The method name can overstate what the rendered visual actually contains. |
| Institutional nodes are generated as generic labels such as `Element 1`, `Element 2`. | `pipeline/staged.py`, `INSTITUTIONAL_DIAGRAM` branch | Institutional relationships lose semantic specificity. |
| Split comparisons are passed hard-coded headings `Dimension A` and `Dimension B`. | `pipeline/staged.py`, `SPLIT_COMPARISON` branch | Generic labels can reach the final frame. |
| Flow diagrams use the fixed heading `CRITERIA / CONDITION TEST`. | `graphics/documentary_animations.py` | A generic template may not accurately represent the scene's actual teaching objective. |
| The storyboard falls back to `Conceptual Framework` when no claim IDs are supplied. | `storyboard/director.py` | This is not a source citation and can mislead viewers about provenance. |
| The storyboard truncates bullet text by character count rather than measuring rendered font bounds and wrapping. | `storyboard/director.py` | Text can be incomplete or clipped. |
| The animation components truncate several labels with fixed slices such as `:52`, `:48`, or `:75`. | `graphics/documentary_animations.py` | Long terms and explanations can be silently cut. |
| Missing timeline/map/chart metadata causes a process-demonstration fallback. | `pipeline/staged.py` | The output can technically render while failing to deliver the intended visual category. The warning must become a release blocker when the visual is essential. |
| The final renderer loops MP4 scene assets to the planned duration and pads/scales them. Transitions are disabled by default. | `video/renderer.py` | Scene assembly works, but does not establish cinematic edit quality or meaningful transitions. |
| The renderer requires each scene's primary asset, but this does not validate the asset's semantic match to narration. | `video/renderer.py` | A valid file can still be the wrong visual. |

### 2.2 Quality gate finding

On `feature/universal-documentary-editorial-standard`, `DocumentaryQualityGate` assigns fixed values to several dimensions, including conceptual clarity, teaching depth, narration naturalness, pronunciation, visual relevance, editing/pacing, and sound quality. Those values are not derived from listening to the audio or inspecting the rendered frames. A gate must not award high scores without observable evidence.

This is a specific audited implementation finding on that branch. It does not prove the same gate is active in the current PR #2 runtime.

### 2.3 CI finding

GitHub Actions run `46169624332` completed with **146 passed, 1 failed, 1 warning**. The failing test was `test_supervisor_does_not_retry_failed_non_idempotent_production`: the test expected `AGENT_01` status `FAILED`, while the runtime returned `BLOCKED`. The deterministic evaluation stage was skipped after the test stage failed. This is not a green build.

Run: https://github.com/keshavs40344/studiofo/actions/runs/46169624332

## 3. Target production standard

The objective is a reference-informed educational documentary workflow, not a promise to reproduce the exact production budget, footage library, or proprietary techniques of a broadcaster or creator.

For every scene, the director must choose the visual form from the teaching objective and available evidence:
- real footage or archive where the specific subject and reuse rights are verified;
- original 2D/3D explanatory reconstruction where a physical or historical mechanism needs visualisation;
- geographically accurate maps for spatial relationships;
- source-linked document/artefact close-ups for primary evidence;
- custom motion graphics for abstract systems and processes;
- charts only when numeric values, units, period, source, and methodology are available;
- concise typography/teaching cards only when text is the most effective teaching form.

A scene must not be silently downgraded to a generic slide when a required asset is missing. It must either receive a suitable fallback that is explicitly labelled and approved, or block release.

## 4. Acceptance checklist — 120 measurable checks

Statuses are deliberately set to **NOT VERIFIED** until evidence is attached. They must not be changed to PASSED merely because a component or test file exists.

### A. Topic planning and coverage

- [ ] **01** Record the exact topic, chapter, audience, language, and intended learning outcome.
- [ ] **02** Store the applicable syllabus/version and research cutoff date.
- [ ] **03** Map every required concept to at least one teaching section.
- [ ] **04** Map every required concept to at least one storyboard scene.
- [ ] **05** Map each concept to a visual requirement or a recorded reason why no visual is needed.
- [ ] **06** Separate prerequisites from advanced material.
- [ ] **07** Separate static knowledge from time-sensitive current affairs.
- [ ] **08** Produce an explicit missing/partial coverage report before rendering.

### B. Research and factual evidence

- [ ] **09** Every material factual claim has a stable claim ID.
- [ ] **10** Every material claim has a source title and issuing body/author.
- [ ] **11** Every source has a URL or persistent document ID.
- [ ] **12** Every source has publication and access dates where available.
- [ ] **13** Every claim has a pinpoint page/section/table/paragraph when the source supports it.
- [ ] **14** Every claim has a supporting excerpt or a recorded reason why one is unavailable.
- [ ] **15** The excerpt is reviewed for actual semantic support, not just keyword overlap.
- [ ] **16** Conflicting claims retain both source definitions and reference periods.
- [ ] **17** Unsupported or outdated high-impact claims are blocked or visibly marked for review.
- [ ] **18** No generated bibliography entry, citation, page number, quotation, statistic, or PYQ is fabricated.

### C. Teaching script and learning design

- [ ] **19** The script teaches meaning and context rather than only listing facts.
- [ ] **20** Important concepts explain what, why, how, components, and consequences as relevant.
- [ ] **21** Technical terms are defined on first use.
- [ ] **22** Hinglish remains natural while preserving standard terminology.
- [ ] **23** Analogies are identified as analogies and their limits are explained.
- [ ] **24** Misconceptions are explicitly addressed where relevant.
- [ ] **25** Examples and case studies are traceable to evidence.
- [ ] **26** Prelims facts and conceptual traps are separately identified.
- [ ] **27** Mains arguments, counterarguments, examples, and answer structure are separately identified.
- [ ] **28** The script has section recaps, transitions, and a coherent conclusion.

### D. Storyboard and scene direction

- [ ] **29** Every scene has one explicit teaching objective.
- [ ] **30** Every scene has a narration-to-visual relationship statement.
- [ ] **31** Every scene has a selected visual archetype with a reason.
- [ ] **32** Every scene identifies its required source-linked assets.
- [ ] **33** Every scene specifies camera/framing/motion only when supported by the asset type.
- [ ] **34** Scene duration is estimated from teaching load and narration pace, not a fixed arbitrary length.
- [ ] **35** No scene contains internal IDs, placeholder labels, or production notes intended only for developers.
- [ ] **36** No generic source label is presented as a real citation.
- [ ] **37** Scene composition varies when the teaching purpose changes.
- [ ] **38** Repeated layouts are flagged for editorial review.
- [ ] **39** Narration and visual cues are synchronised to the same concept and time window.
- [ ] **40** The storyboard is reviewed before long-form rendering.

### E. Visual asset research, provenance, and rights

- [ ] **41** Each external asset has its creator/issuer recorded.
- [ ] **42** Each external asset has an origin URL or source document ID.
- [ ] **43** Each external asset has a verified licence/permission status for intended use.
- [ ] **44** Required attribution text is stored and rendered where required.
- [ ] **45** Retrieval date and asset hash are stored.
- [ ] **46** Assets with unknown rights are excluded from approved export.
- [ ] **47** Generic stock footage is not represented as a specific historical event, person, site, or artefact.
- [ ] **48** Historical reconstructions are labelled as reconstructions, not primary evidence.
- [ ] **49** AI-generated illustrative imagery is labelled internally and is not used as factual source evidence.
- [ ] **50** Primary-source scans and artefact images retain enough context to identify the source.
- [ ] **51** Visual assets are checked for relevance to the exact narration passage.
- [ ] **52** Missing/low-quality assets produce a visible review item and do not silently become unrelated placeholders.

### F. Maps, charts, diagrams, and animation

- [ ] **53** A geographic map uses real geographic geometry or a verified basemap, not only region-name cards.
- [ ] **54** Maps include a legend, scale/context where relevant, date/version, and source.
- [ ] **55** Borders and boundaries match the selected historical/current date.
- [ ] **56** Routes, rivers, regions, and coordinates are based on supplied/verified data.
- [ ] **57** Charts require numeric values, units, period, source, and methodology.
- [ ] **58** Chart axes and scales are checked for misleading presentation.
- [ ] **59** Institutional diagrams use real institution/office names and verified relationships.
- [ ] **60** Cause-effect diagrams distinguish evidence-backed causation from correlation or interpretation.
- [ ] **61** Before/after labels describe actual comparison dimensions, not generic Dimension A/B labels.
- [ ] **62** Flowcharts use labels from the actual process or law, not a generic template heading.
- [ ] **63** Scientific illustrations represent the relevant mechanism and are reviewed for conceptual correctness.
- [ ] **64** Historical timelines use verified dated events and source citations.
- [ ] **65** No default/sample dates, regions, numbers, or milestones appear in production output.
- [ ] **66** 2D/3D motion is continuous where specified; frame-by-frame holds are not misreported as camera animation.
- [ ] **67** Camera moves, parallax, depth, and scene transitions have a declared purpose.
- [ ] **68** Visual changes occur at concept boundaries and allow sufficient reading time.
- [ ] **69** Every animation is checked for a complete first, middle, and final frame.
- [ ] **70** A missing animation dependency or asset produces an explicit blocked/degraded status.

### G. Editing, rendering, and continuity

- [ ] **71** The opening establishes the question/problem and the learning promise.
- [ ] **72** Section changes are editorially motivated rather than random effects.
- [ ] **73** Each rendered shot has a valid source asset and scene ID.
- [ ] **74** Every scene is checked against its planned duration.
- [ ] **75** Repeated/duplicate visual shots are detected.
- [ ] **76** Black frames, frozen frames, corrupted segments, and unintended gaps are detected.
- [ ] **77** Aspect ratio, safe areas, resolution, frame rate, and pixel format are validated.
- [ ] **78** Text and graphics remain inside title/subtitle safe zones.
- [ ] **79** Final video duration is compared with narration and storyboard duration.
- [ ] **80** The exact rendered file is inspected, not just intermediate stills or mocked outputs.

### H. Narration and sound design

- [ ] **81** The default narration source is the creator's own recording when supplied.
- [ ] **82** Missing creator narration places the project in WAITING_FOR_VOICE unless the creator explicitly enables another voice.
- [ ] **83** Audio is checked for clipping, distortion, dropouts, and unintended silence.
- [ ] **84** Loudness and true peak are measured and reported.
- [ ] **85** Speech remains natural; processing does not materially distort voice identity or intelligibility.
- [ ] **86** Pronunciation is reviewed for names, places, dates, acronyms, and technical terms.
- [ ] **87** Ambient sound, effects, and music have provenance/licensing recorded.
- [ ] **88** Music/effects are mixed beneath narration and ducked when appropriate.
- [ ] **89** Sound transitions match visual transitions and narrative emphasis.
- [ ] **90** Final audio is listened to in full or reviewed with an explicit human sign-off; metadata alone is insufficient.

### I. Subtitles and accessibility

- [ ] **91** Subtitles are generated from the final approved narration/transcript.
- [ ] **92** Subtitle timing is aligned to actual speech.
- [ ] **93** Subtitles are checked for Devanagari shaping and Latin/Hinglish code-switching.
- [ ] **94** Subtitle reading speed and line length are checked.
- [ ] **95** Names, numbers, dates, units, and terminology match the approved script.
- [ ] **96** Contrast and text-size checks are applied to captions and on-screen text.
- [ ] **97** Important meaning is not conveyed by colour alone.
- [ ] **98** No subtitle overlaps critical labels or essential on-screen content.
- [ ] **99** Optional language tracks are marked available only when translation and target voice models are installed and reviewed.
- [ ] **100** Each dubbed track has its own pronunciation, timing, subtitle, and audio QA result.

### J. Automated visual/audio/academic QA

- [ ] **101** The final video is scanned for forbidden placeholder strings.
- [ ] **102** OCR/frame inspection checks for clipped or truncated visible text.
- [ ] **103** Scene-level checks compare the rendered asset type with the storyboard requirement.
- [ ] **104** Image/video similarity checks identify suspiciously repeated scenes.
- [ ] **105** Maps/charts are revalidated against their structured source data.
- [ ] **106** Frame sampling covers intro, each section transition, every scene midpoint, and the ending.
- [ ] **107** Audio/video sync is measured against actual narration and scene timestamps.
- [ ] **108** The QA report lists evidence, failures, warnings, and untested items per gate.
- [ ] **109** A visual quality score is never hard-coded or inferred from a storyboard declaration.
- [ ] **110** A passing file-exists/size test is never reported as proof of editorial quality.
- [ ] **111** Any hard blocker prevents READY_FOR_PUBLICATION.
- [ ] **112** Human academic review, rights review, technical review, and final creator approval remain separate statuses.

### K. Study materials and release outputs

- [ ] **113** Full chapter notes are generated from the approved research/script.
- [ ] **114** Concise revision notes, glossary, and concept map are generated and cross-checked.
- [ ] **115** Practice questions are labelled as generated practice, not authentic PYQs.
- [ ] **116** Authentic PYQs have source/year/question references and verified wording.
- [ ] **117** Thumbnail, title, description, chapters, tags, and pinned-comment draft match the actual chapter.
- [ ] **118** Upload stays disabled/private until explicit per-run creator approval and all required gates pass.
- [ ] **119** Release package includes final video, subtitle files, sources/evidence, rights ledger, QA reports, and version hashes.
- [ ] **120** Unresolved defects and unverified requirements are listed in the release report.

## 5. Required visual QA behaviours

The visual QA stage must inspect the rendered media and structured inputs. It should detect, at minimum:
- literal placeholders such as `Element 1`, `Dimension A`, `Dimension B`, `Conceptual Framework`, `+ name`, `date`, `label`, and equivalent template tokens;
- text beyond the rendered frame boundary, clipped glyphs, overflow, unreadable font sizes, and subtitle collisions;
- map scenes that contain no map geometry; chart scenes that contain no chart data; and diagrams whose labels do not correspond to the underlying topic;
- repeated scene images/near-identical compositions beyond an approved threshold;
- missing visual assets, broken MP4 segments, black/frozen frames, invalid duration, and narration desynchronisation;
- absent source/period/unit/legend metadata on evidence graphics.

OCR may be one signal, but it is not sufficient alone. The QA must combine structured metadata, deterministic geometry/asset checks, media probing, representative frame inspection, and human review for semantic correctness.

## 6. Implementation sequence

### P0 — Stop invalid output from passing
1. Remove synthetic/default production data and misleading citation fallbacks.
2. Make required visual metadata failures explicit.
3. Add placeholder-string regression tests.
4. Add text measurement/wrapping and frame-boundary checks.
5. Replace fixed quality scores with evidence-backed assessments or HUMAN_REVIEW_REQUIRED.
6. Make visual QA run on the final encoded MP4, not only storyboard objects.
7. Fix and rerun the current failing CI test without weakening runtime safety semantics.

### P1 — Make visuals match the topic
1. Build a typed visual-asset request schema per scene.
2. Connect source discovery, asset download/import, attribution, rights review, and cache hashes.
3. Implement real geographic map rendering with verified boundary/route data.
4. Replace generic institutional/cause-effect/process headings with structured semantic data.
5. Add a visual selection rule that can choose footage, map, archive, illustration, diagram, chart, typography, or 3D reconstruction.
6. Require manual review for reconstructions or potentially misleading depictions.

### P2 — Upgrade documentary editing
1. Add a timeline model for shot types, voiceover, b-roll, overlays, transitions, and sound cues.
2. Add restrained motion design, camera moves, layered parallax, map animation, and scene-specific compositions.
3. Support licensed footage and original visual assets without treating either as automatically available.
4. Preserve CPU-safe proxy rendering and offer optional external rendering where local hardware is insufficient.
5. Maintain actual scene continuity and narration pacing.

### P3 — Validate the full learning product
1. Use Indus Valley Civilization as the first visual acceptance project.
2. Produce a short representative pilot before rendering a full chapter.
3. Review every shot against a timecoded storyboard and source record.
4. Validate academic coverage, source quality, voice, subtitles, and all derived study materials.
5. Render the full chapter only after the pilot passes.
6. Keep publication approval manual.

## 7. First pilot acceptance deliverables

The Indus Valley pilot should include, only where supported by evidence and rights:
- an opening that poses a clear historical question;
- a correctly located Indus/Harappan site map with a readable legend and source;
- distinct site/artefact visuals with accurate captions;
- an original reconstruction clearly labelled as reconstruction;
- a real explanatory visual for urban planning/drainage rather than generic text boxes;
- a chronology built from verified dated events;
- a trade/geography visual only where source data supports it;
- a concise evidence/source card for important disputed claims;
- natural narration, aligned subtitles, deliberate sound design, and coherent scene transitions;
- a complete visual QA report with representative frame evidence.

A missing asset must be reported as missing; it must not be replaced by invented facts, placeholder text, or an unrelated generic slide.

## 8. Audit status

- Reference URLs recorded: **8/8**.
- Reference videos watched frame-by-frame: **NOT VERIFIED**.
- Repository code inspection: **PARTIAL; focused on storyboard, visuals, renderer, QA, docs, and CI evidence**.
- Acceptance checks written: **120**.
- Acceptance checks passed against an actual production video: **NOT VERIFIED**.
- Production readiness: **NOT ESTABLISHED**.

This document is an audit baseline and acceptance contract. It is not an implementation-complete claim. Each check must be linked to a real code path, executed test or inspected media artifact before it can be marked passed.
