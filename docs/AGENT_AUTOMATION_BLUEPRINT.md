# Agent & Automation Expansion Blueprint

## Current verified baseline

The repository already contains:
- a 24-entry agent registry in `src/upsc_studio/agents/contracts.py`;
- a supervisor in `src/upsc_studio/agents/supervisor.py`;
- six task skills under `.agents/skills/`;
- a chapter pipeline and QA modules;
- a local-first end-to-end production skill.

Important limitation: registry entries are mappings to existing modules, not proof of 24 independent autonomous workers. Several entries reuse the same module, and the current supervisor primarily invokes the chapter pipeline plus editorial packaging and a YouTube upload check. Do not advertise all 24 as independently implemented agents until each has its own validated contract, execution path, tests and observable outputs.

Evidence-integrity hardening is documented separately in `docs/AGENT_EVIDENCE_INTEGRITY.md`. Source candidates are not treated as verified facts; claim verification requires a reviewer-declared excerpt and pinpoint reference. The local API currently records a reviewer label but does not authenticate the reviewer's identity. The production pipeline pauses in `WAITING_FOR_RESEARCH_REVIEW` until claims are attested, and teaching generation fails closed when no attested factual claims exist.

## Recommended agent topology

Use a supervisor + specialist workers + independent validators.

### Planning and research
1. Executive Producer — owns project state, dependencies, checkpoints and final report.
2. Topic Classifier — selects UPSC, GK, current affairs or deep dive.
3. Curriculum Mapper — maps syllabus only when the project is UPSC.
4. Learning Objective Designer — defines measurable learning outcomes.
5. Research Planner — identifies missing information and source requirements.
6. Source Collector — gathers source material through permitted connectors/tools.
7. Evidence Extractor — converts source text into atomic claims.
8. Independent Fact Checker — checks support, contradictions, dates and uncertainty.
9. Coverage Auditor — checks every required concept against explanation and evidence.

### Teaching and editorial
10. Teaching Architect — structures prerequisite-to-advanced explanation.
11. Scriptwriter — writes the Hinglish master script.
12. Red-Team Editor — identifies gaps, ambiguity, weak explanations and unsupported claims.
13. Exam Specialist — adds Prelims/Mains relevance only for UPSC projects.
14. Retention Editor — improves pacing without distorting facts or adding filler.
15. Language/Pronunciation Editor — validates names, acronyms, numbers and transliteration.

### Visual, audio and production
16. Storyboard Director — maps each teaching concept to a visual treatment.
17. Map Specialist — generates maps only when geography/spatial relationships matter.
18. Data Graphics Specialist — produces charts from cited data.
19. Motion Graphics Specialist — creates mechanism/process animations.
20. Asset Rights Auditor — checks provenance and licence status.
21. Narration/Audio Worker — processes approved user voice or explicitly enabled TTS.
22. Subtitle/Accessibility Worker — creates and checks captions and accessibility outputs.
23. Render Worker — assembles resumable scene-based video.
24. Final Release Auditor — independently checks academic, rights, audio, visual and export gates.

YouTube packaging and analytics should be separate post-production services, not allowed to bypass the release auditor.

## Automation controls

- Dependency-aware DAG; only run independent tasks concurrently.
- Idempotency key per project + stage + input hash to prevent duplicate work.
- Persist task status, timestamps, retries, errors, input/output references and software versions.
- Retry transient network/process errors only; do not retry validation failures blindly.
- Checkpoint every expensive stage; resume without regenerating successful assets.
- Use CPU-safe concurrency defaults for the supported laptop.
- Record model/tool versions and source access dates for reproducibility.
- Treat downloaded repository code and source documents as untrusted input; never execute arbitrary scripts from a discovered repo automatically.
- Require explicit approval for paid APIs, external account access, voice cloning and public upload.
- Never put tokens, API keys, private source files or personal voice recordings in logs or Git.

## Required acceptance tests before calling the system autonomous

- UPSC Fundamental Rights: syllabus mapping and all declared constitutional concepts accounted for.
- GK science topic: no irrelevant UPSC boilerplate; mechanism explained at appropriate depth.
- Current affairs: cutoff date visible; claims have dated sources; stale items flagged.
- Deep dive: no dependency on UPSC syllabus data.
- Omission injection: remove one required concept and ensure coverage audit fails.
- Evidence injection: unsupported claim must be REVIEW_REQUIRED or FAIL.
- Duplicate job: same idempotency key must not start a second active render.
- Retry: transient failure retries within configured limit; permanent failure does not.
- Resume: successful stages are reused after interruption.
- Rights: unverified asset blocks release.
- Voice absent: pipeline reports WAITING_FOR_VOICE, not completed video.
- Publishing: no public upload without explicit human approval.

## Status semantics

A registry row, prompt, skill file or workflow definition is not an implemented agent by itself. An agent is implemented only when it has a real executable path, typed input/output contract, persisted task record, failure handling, tests and auditable output. A workflow is active only when its trigger actually runs it. Report these states separately.
