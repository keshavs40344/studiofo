---
name: academic-video-qa
description: Audits chapter completeness, claim evidence, teaching logic, syllabus alignment, asset rights, subtitles, audio, scene continuity and final video integrity before approval.
---
# Academic and Video QA

## Academic checks
- Every required syllabus item maps to an explanation and scene or is justified as not applicable.
- Every important factual statement has a claim ID and supporting inspected source.
- No unsupported or conflicting high-impact claim is presented as fact.
- Dates, laws, constitutional articles, statistics, schemes, reports and judgments are checked against authoritative sources.
- PYQs are authentic and source-linked; generated practice questions are labelled.
- Prelims/Mains/CSAT distinctions are correct.
- Concepts are explained, not merely mentioned.
- Current affairs cutoff and reference periods are visible.

## Teaching checks
- Coherent progression from basic to advanced.
- Definitions and unfamiliar terms explained.
- Examples relevant and accurate.
- Appropriate caveats, counterarguments and analysis included.
- Recaps and assessments match taught content.

## Media and rights checks
- Every included external asset has verified usage rights and provenance.
- No broken paths, missing media, incorrect labels, generic footage presented as a specific fact, unreadable text or cropped graphics.
- Charts/maps have sources, date/version, units/legend and calculations checked.
- Animations and transitions support comprehension and are not distracting.

## Audio and export checks
- Narration complete and intelligible; no clipping/dropouts or unintended silence.
- Music ducked appropriately and licensed.
- Subtitles match actual speech, are timed, readable and render Hindi correctly.
- Export opens and plays; inspect duration, frame rate, resolution, audio streams, black/frozen frames where detectable and file integrity.

## Release statuses
Use separate statuses: ACADEMICALLY_REVIEWED, RIGHTS_CLEARED, VIDEO_TECHNICALLY_APPROVED and READY_FOR_PUBLICATION. Do not mark any status without evidence. Unresolved blocking issues prevent the relevant approval. Provide a defect list with severity, affected claim/scene and remediation.

Deliverables: `academic_qa.json`, `rights_qa.json`, `media_qa.json`, `release_readiness.md`.
