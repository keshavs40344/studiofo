# Model Training, Calibration and Release Evaluation Protocol

## Accuracy boundary

No finite training set, prompt, test suite or automation can establish a zero probability of error. The system must never claim perfection. It must expose uncertainty, abstain when evidence is missing, and block release when a critical gate fails.

## Current implementation state

The repository currently has deterministic validation workers and a test/evaluation harness. This is NOT fine-tuning or training of a foundation model. No training corpus, selected base model, tokenizer, GPU training environment, or model-serving target has been approved or supplied. Therefore model-weight training is not performed by this change.

## Required data before fine-tuning

For every training example, retain:
- task category and language;
- user-authorized input text and source references;
- expected output in a versioned schema;
- expert-reviewed correctness label and reviewer identity/role;
- evidence date and source licence/permission;
- known ambiguity and acceptable abstention response.

Do not put private voice recordings, API keys, personal data, copyrighted books or unlicensed media into a training set. Deduplicate near-identical examples. Keep a held-out test set that is never used for training or prompt tuning. Split by source/document and time, not random adjacent passages, to reduce leakage.

## Evaluation gates

1. Schema validity: every response parses and validates.
2. Evidence grounding: each factual claim links to a traceable source; missing evidence means REVIEW_REQUIRED.
3. Temporal correctness: current-affairs claims respect the project's explicit cutoff.
4. Coverage: every declared learning objective and required concept is accounted for.
5. Contradiction review: conflicting evidence is surfaced, not silently resolved.
6. Teaching quality: prerequisites, definitions, mechanism, examples, limitations and recap are evaluated by a separate rubric.
7. Language QA: names, dates, numbers, acronyms and pronunciation are checked.
8. Visual QA: visual claims match the narration; provenance and rights are recorded.
9. Media QA: audio/video duration, black frames, silent segments, caption timing and file integrity are checked.
10. Adversarial QA: malformed inputs, prompt injection in source documents, misleading citations, missing sections and contradictory instructions are tested.
11. Regression QA: all golden cases run on every change.
12. Human release approval: required for final release and any public upload.

## Multi-pass workflow

- Pass A: producer creates a plan and a list of claims/objectives.
- Pass B: research worker collects evidence; every source is recorded with publication/access dates.
- Pass C: independent verifier checks claim-to-source support and flags conflict/staleness.
- Pass D: writer creates the teaching explanation from verified evidence.
- Pass E: coverage auditor checks required concepts and learning objectives.
- Pass F: red-team reviewer attempts to find omissions, ambiguity, unsupported inference and misleading simplification.
- Pass G: production workers create visuals/audio/video from approved script.
- Pass H: independent media, rights and academic gates run.
- Pass I: final report records passed/failed/review-required gates and unresolved issues.

A second pass must be meaningfully independent: it must not simply repeat the same model prompt and accept its own previous answer. Where no independent source or reviewer is available, label the result as not independently verified.

## Release policy

- Critical unsupported factual claim: BLOCK.
- Missing citation for material factual claim: REVIEW_REQUIRED or BLOCK according to severity.
- Unverified asset rights: BLOCK.
- Failed render integrity or media gate: BLOCK.
- Current affairs without cutoff date: BLOCK.
- Missing required concept: BLOCK or return to script revision.
- Model disagreement or low confidence: REVIEW_REQUIRED.
- No public upload without explicit human approval.

## Fine-tuning approval checklist

Before any weight update, select and document the base model, model licence, hardware budget, dataset provenance, data protection plan, train/validation/test split, objective, evaluation metrics, rollback checkpoint and deployment target. Compare the candidate against the unchanged baseline on the frozen test set. Reject the candidate if factual accuracy, abstention calibration, language quality, latency or resource use regresses.
