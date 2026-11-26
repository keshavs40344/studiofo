# Universal Documentary Editorial Standard

Status: implementation specification. This document defines acceptance requirements; it does not claim that every requirement is implemented.

## Editorial contract

- Master narration language: Hinglish by default.
- Format: documentary-teacher hybrid. Explain the subject with evidence, causal links, examples, timelines, maps, diagrams and recaps where relevant.
- Supported content domains: UPSC syllabus topics, general knowledge, current affairs, and standalone deep dives.
- A video must teach its declared scope. Do not pad runtime with generic material or unrelated UPSC/constitution explanations.
- Never claim complete coverage unless every required concept in the approved topic map has passed the coverage audit.

## Topic planning and coverage

Before scripting, create a topic map containing:
- learning objectives and prerequisite concepts;
- required subtopics and key terms;
- chronology, actors, institutions, mechanisms and cause/effect links where applicable;
- examples, case studies and counterexamples where they materially aid understanding;
- common misconceptions and exam-relevant distinctions;
- source/evidence requirements and unresolved questions.

Each required concept must map to:
1. a script passage that explains it;
2. at least one suitable visual or an explicit reason a visual is unnecessary;
3. supporting source/evidence when factual;
4. a QA result: PASS, REVIEW_REQUIRED, or FAIL.

A concept is not covered merely because its name appears in narration or on screen.

## Research and factual integrity

- Separate established facts, interpretation, disputed claims and unknowns.
- Record source title, publisher, URL, publication date, access date and the claims supported.
- Current-affairs scripts must state a research cutoff date and distinguish developments by date.
- Do not invent citations, statistics, quotations, events or source details.
- If evidence is insufficient or sources materially conflict, mark REVIEW_REQUIRED and do not present the claim as settled.
- High-impact factual claims require independent corroboration appropriate to the claim.

## Script and visual quality

- Explain technical terms at first meaningful use.
- Prefer concrete explanations over lists of facts.
- Visuals must clarify the concept: maps for spatial relationships, timelines for chronology, diagrams for mechanisms, charts for quantitative comparisons, and labelled illustrations for structure.
- Do not use decorative stock footage as a substitute for explaining a concept.
- Avoid repetitive intros, generic transitions, filler and unsupported dramatic claims.
- Pronunciation, names, dates, units and acronyms must be checked before rendering.

## Language and dubbing

- Produce and QA the Hinglish master first.
- Additional languages are separate localized tracks, not merely translated subtitles.
- Preserve meaning, names, figures, units, tone and pronunciation across dubs.
- Do not claim 10+ language availability until each language has a generated, reviewed and playable audio track.
- Do not describe synthetic speech as human-recorded or indistinguishable from a human voice.

## Release gates

A render is not publish-ready unless:
- required topic coverage is audited;
- factual claims have evidence or are explicitly flagged;
- narration and subtitles are synchronized;
- audio is intelligible and pronunciation checks pass;
- visual assets have provenance/licensing recorded;
- export duration, frame rate, resolution and audio stream are validated;
- a human approval step is completed before public upload.

## Honest status reporting

Report implemented, tested, partially implemented, blocked and not implemented separately. A passing unit test is not proof of editorial completeness or production quality. Never fabricate a score or mark an unrun test as passed.
