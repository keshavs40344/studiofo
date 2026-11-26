---
name: research-verification
description: Performs UPSC educational research, current-affairs updates and claim-level evidence verification using official and reputable sources; flags unsupported, outdated or conflicting material.
---
# Research and Verification

1. Set and display the research cutoff date and target exam cycle.
2. Prefer primary official sources for constitutional/legal text, policies, schemes, official statistics, reports, budgets, judgments and institutional facts.
3. Use academic and reputable secondary sources for context and interpretation; label opinion separately.
4. Decompose material script statements into atomic claims.
5. For each claim store claim ID, exact statement, source title, organisation/author, URL/document ID, publication date, access date, relevant page/section/table, reference period, evidence excerpt/summary and status.
6. Use only these statuses: VERIFIED, PARTIALLY_VERIFIED, CONFLICTING, OUTDATED, UNSUPPORTED, HUMAN_REVIEW_REQUIRED.
7. A reachable URL is not sufficient. Inspect whether the source actually supports the claim.
8. Cross-check legal provisions against current official texts and statistics against original tables where possible.
9. Preserve definitions, units, reference periods and methodological notes when different sources disagree.
10. Never invent citations, quotations, statistics, committees, reports, PYQs or source metadata.
11. Block unsupported high-impact facts from final narration, or clearly route them to human review. Never silently fill gaps.
12. Save a bibliography and a claim-to-source ledger linked to script paragraphs and scenes.

Deliverables: `evidence_ledger.json`, `sources.bib.json`, `verification_report.md`, `unresolved_claims.md`.
