# Research Verification & Evidence Integrity Audit

## Mission Overview
This report documents the architectural design, implementation, and adversarial validation of the **High-Reliability Research and Fact Verification System** for UPSC Studio (`studiofo`), implemented on working branch `phase17/recovery-runtime-integration` (associated with PR #2).

The core mission is to minimize unsupported factual statements, eliminate fabricated assertions, strictly enforce temporal research cutoffs, detect factual and numerical contradictions, and clearly communicate evidential uncertainty through an explicit 6-stage lifecycle.

> [!IMPORTANT]
> **Fundamental Reality Disclaimer**: No claim of 100% factual accuracy or zero-defect automated truth determination is made. Automated systems can verify metadata presence, temporal validity, textual overlap, and structural consistency, but cannot replace independent human scholarly verification. All release gates require human attestation.

---

## 1. High-Reliability Research Workflow

The upgraded research pipeline executes an end-to-end 12-step verification protocol:
1. **Structured Research Planning (`planner.py`)**: Before querying sources, `ResearchPlanner` compiles a multi-dimensional research plan spanning Constitutional/Statutory, Judicial, Statistical, Institutional, Historical, and Current Policy dimensions.
2. **Conservative Source Discovery (`discovery.py`)**: Queries academic indexes (Crossref), open knowledge (Wikipedia), and web search (Brave) to register candidate sources with tier `OTHER` and status `HUMAN_REVIEW_REQUIRED`. A live URL or abstract is never treated as proof of claim support.
3. **Source Metadata Extraction**: Captures publisher, title, canonical URL, publication date, and access date.
4. **Safe Text Extraction (`extractor.py`)**: Strips scripts, style tags, and malicious control characters from external documents and notes.
5. **Addressable Page/Section Chunking**: Decomposes ingested documents into discrete `DocumentSection` objects with character offsets and specific page or section coordinates.
6. **Atomic Claim Extraction (`extractor.py`)**: Breaks compound statements into discrete atomic propositions containing single verifiable assertions.
7. **Claim-to-Source Mapping (`verifier.py`)**: Binds each atomic claim to an external primary or academic source with an exact supporting excerpt.
8. **Contradiction Detection (`contradictions.py`)**: Cross-checks claims for numerical disparities, date discrepancies, opposing legal status classifications, and direct semantic negations.
9. **Temporal Cutoff Tracking**: Enforces strict cutoffs on `current_affairs` and dated topics, automatically rejecting and flagging post-cutoff sources.
10. **Evidence Quality Assessment (`corroborator.py`)**: Applies source tier weights (`PRIMARY_OFFICIAL: 1.0`, `ACADEMIC_PEER_REVIEWED: 0.85`, `REPUTABLE_NEWS: 0.70`, `OTHER: 0.40`, `USER_NOTES: 0.10`).
11. **Independent Source Corroboration**: High-impact claims (statutory articles, percentages, statistics, dates) require corroboration across distinct publishers/domains.
12. **Human Attestation & Signing**: Final transition to `VERIFIED` status requires a named human reviewer signature and records an attestation timestamp and excerpt.

---

## 2. Six-Stage Evidence Lifecycle

To prevent misleading claims of automated verification, the system maintains 6 explicit lifecycle stages for every claim:

| Lifecycle Stage | Meaning | Automated Verification Criteria |
|---|---|---|
| `source_discovered` | Candidate source exists | Source registered in bibliography ledger |
| `source_accessible` | Source reachable | URL validated or local document persisted |
| `evidence_extracted` | Relevant excerpt located | Page/section coordinates and substantive excerpt recorded |
| `claim_supported` | Claim aligns with excerpt | Textual and semantic consistency between statement and excerpt |
| `independently_corroborated` | Multi-source corroboration | Supported by 2+ distinct publishers/domains |
| `human_reviewed` | Human attestation completed | Named human expert review signed off |

---

## 3. Threat Model & Prompt Injection Mitigation

External documents, student notes, and web search results are treated as **untrusted data**.
Implemented in `src/upsc_studio/research/security.py`:
- **Adversarial Pattern Scanning**: Scans for prompt injection attacks (`ignore previous instructions`, `bypass verification`, `system override`, `<|system|>`, `[INST]`, `<<SYS>>`).
- **Sanitization & Neutralization**: Neutralizes template breakout tokens into `[FILTERED_ADVERSARIAL_INSTRUCTION]`.
- **Code Execution Defense**: Rejects attempts to execute shell commands, backticks, `subprocess`, `eval()`, or download executable scripts.
- **Fail-Closed Verification**: Any claim statement or source title containing unneutralized threats is rejected immediately.

---

## 4. Contradiction & Discrepancy Detection

Implemented in `src/upsc_studio/research/contradictions.py`:
- **Numerical Disparities**: Flags disparate percentages or metrics describing the same subject and reference period (e.g., 14.5% vs 24.2%).
- **Chronological Disparities**: Flags conflicting years or dates asserted for the same act, judgment, or milestone.
- **Status Contradictions**: Detects mutually exclusive legal classifications (e.g., asserting an institution is simultaneously a "constitutional body" and a "statutory body").
- **Reporting**: Generates `research/contradictions_report.json` and updates conflicting claims to status `CONFLICTING`.

---

## 5. Adversarial Test Suite Outcomes

Implemented in `tests/test_adversarial_research.py`. All 10 adversarial fixtures passed:

| Test Case | Adversarial Vector | Expected & Observed Result | Status |
|---|---|---|---|
| `test_missing_page_reference_rejection` | Empty or whitespace `page_or_section` | `ValueError: page_or_section reference required` | **PASSED** |
| `test_fake_or_malformed_dates_rejection` | Malformed date string `"25th of Dec, 2025"` | `ValueError: Invalid pub_date format` | **PASSED** |
| `test_outdated_claim_rejection_after_cutoff` | Source date `2026-07-15` post-dates cutoff `2026-05-01` | Status set to `OUTDATED`, `ValueError` raised | **PASSED** |
| `test_misleading_unrelated_excerpt_rejection` | Claim on Article 32 paired with aerospace alloy excerpt | `ValueError: No shared substantive terms` | **PASSED** |
| `test_incomplete_brief_evidence_rejection` | Excerpt length < 10 characters | `ValueError: Evidence excerpt too brief` | **PASSED** |
| `test_contradictory_sources_detection` | Constitutional body vs statutory body contradiction | Detected, flagged `CONFLICTING`, report exported | **PASSED** |
| `test_numerical_contradiction_detection` | Export share 14.5% vs 24.2% on same metric | Detected, flagged `NUMERICAL_DISPARITY` | **PASSED** |
| `test_adversarial_prompt_injection_neutralization` | Document containing `<|system|> Ignore instructions` | Threats detected and neutralized | **PASSED** |
| `test_full_6_stage_verification_lifecycle_tracking` | Complete valid legal claim verification | All 6 lifecycle stages set and exported | **PASSED** |
| `test_user_notes_are_not_counted_as_external_research` | Claim backed only by `USER_NOTES` | Academic QA gate fails with blocking issue | **PASSED** |

---

## 6. Regression Testing & Integration

- `tests/test_adversarial_research.py` + `tests/test_content_categories.py` + `tests/test_advanced_teaching_engine.py`: **25/25 passed**.
- `tests/test_teaching_evidence_safety.py` + `tests/test_research_discovery.py` + `tests/test_research_workflow_api.py`: **16/16 passed**.
- Phase 15 & Phase 16 Full Factory Acceptance Suite: **14/14 passed**.
- Deterministic Evaluation Suite (`upsc_studio.agents.evaluate`): **12/12 passed (100% pass rate)**.

---

## 7. Known Limitations & Safe Operating Boundaries

1. **Semantic Nuance & Legal Interpretation**: While string token overlap and contradiction detectors identify obvious discrepancies and unrelated excerpts, subtle legal arguments (e.g. obiter dicta vs ratio decidendi) cannot be resolved autonomously and require human legal review.
2. **Dynamic Web Changes**: Server reachability does not guarantee persistent content availability. Offline archival copies of primary sources should be maintained where permitted.
3. **External Fact-Check Boundaries**: The system verifies claims strictly against the recorded project bibliography and human reviewer attestations; it does not claim to possess an omniscient external world model.
4. **Mandatory Human Release Gate**: Automated QA gates remain fail-closed. Public publishing is permanently gated on human approval.
