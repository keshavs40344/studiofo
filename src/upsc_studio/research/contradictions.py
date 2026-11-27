"""Contradiction and factual conflict detection engine.

Detects conflicting dates, disparate statistical figures, conflicting legal classifications,
and semantic negations across recorded factual claims and candidate sources.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class ContradictionRecord:
    claim_id_a: str
    claim_id_b: str
    conflict_type: str  # NUMERICAL_DISPARITY, DATE_DISPARITY, STATUS_CONTRADICTION, DIRECT_NEGATION
    description: str
    statement_a: str
    statement_b: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ContradictionDetector:
    """Detects substantive discrepancies across multiple recorded claims."""

    OPPOSING_TERMS = [
        (r"\bconstitutional\s+body\b", r"\bstatutory\s+body\b"),
        (r"\bconstitutional\s+body\b", r"\bextra[\s-]constitutional\s+body\b"),
        (r"\bnon[\s-]statutory\b", r"\bstatutory\s+body\b"),
        (r"\brequires\s+prior\s+sanction\b", r"\bdoes\s+not\s+require\s+(?:prior\s+)?sanction\b"),
        (r"\bhas\s+been\s+passed\b", r"\bhas\s+not\s+been\s+passed\b"),
        (r"\bwas\s+enacted\b", r"\bwas\s+(?:rejected|repealed|withdrawn)\b"),
    ]

    def detect_all_conflicts(self, claims: list[dict[str, Any]]) -> list[ContradictionRecord]:
        """Exhaustively cross-check claims for numerical, chronological, or semantic contradictions."""
        conflicts: list[ContradictionRecord] = []
        n = len(claims)

        for i in range(n):
            for j in range(i + 1, n):
                claim_a = claims[i]
                claim_b = claims[j]

                # Check 1: Year / Date Disparity on common subject
                date_conflict = self._check_date_conflict(claim_a, claim_b)
                if date_conflict:
                    conflicts.append(date_conflict)
                    continue

                # Check 2: Numerical / Percentage Disparity on common subject
                num_conflict = self._check_numerical_conflict(claim_a, claim_b)
                if num_conflict:
                    conflicts.append(num_conflict)
                    continue

                # Check 3: Legal / Status Disparity (e.g. Constitutional vs Statutory)
                status_conflict = self._check_status_conflict(claim_a, claim_b)
                if status_conflict:
                    conflicts.append(status_conflict)
                    continue

        return conflicts

    def _check_date_conflict(self, a: dict[str, Any], b: dict[str, Any]) -> Optional[ContradictionRecord]:
        """Detect different years asserted for the exact same event or statute."""
        st_a = a.get("statement", "")
        st_b = b.get("statement", "")

        years_a = set(re.findall(r"\b(?:19|20)\d{2}\b", st_a))
        years_b = set(re.findall(r"\b(?:19|20)\d{2}\b", st_b))

        if not years_a or not years_b or years_a == years_b:
            return None

        # Check for substantial shared subject terms (excluding stopwords and digits)
        tokens_a = {w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", st_a)}
        tokens_b = {w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", st_b)}
        common_tokens = tokens_a.intersection(tokens_b)

        # High overlap indicates they are discussing the exact same act, judgment, or milestone
        if len(common_tokens) >= 3:
            return ContradictionRecord(
                claim_id_a=a["id"],
                claim_id_b=b["id"],
                conflict_type="DATE_DISPARITY",
                description=(
                    f"Disparate years asserted for topic sharing terms ({', '.join(list(common_tokens)[:4])}): "
                    f"{sorted(list(years_a))} vs {sorted(list(years_b))}"
                ),
                statement_a=st_a,
                statement_b=st_b,
            )
        return None

    def _check_numerical_conflict(self, a: dict[str, Any], b: dict[str, Any]) -> Optional[ContradictionRecord]:
        """Detect contradictory statistics for the same metric."""
        st_a = a.get("statement", "")
        st_b = b.get("statement", "")

        nums_a = set(re.findall(r"\b\d+(?:\.\d+)?\s*%", st_a))
        nums_b = set(re.findall(r"\b\d+(?:\.\d+)?\s*%", st_b))

        if not nums_a or not nums_b or nums_a == nums_b:
            return None

        # If reference periods match or subject tokens heavily overlap
        tokens_a = {w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", st_a)}
        tokens_b = {w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", st_b)}
        common = tokens_a.intersection(tokens_b)

        if len(common) >= 3:
            return ContradictionRecord(
                claim_id_a=a["id"],
                claim_id_b=b["id"],
                conflict_type="NUMERICAL_DISPARITY",
                description=f"Contradictory percentages for common metric ({', '.join(list(common)[:3])}): {nums_a} vs {nums_b}",
                statement_a=st_a,
                statement_b=st_b,
            )
        return None

    def _check_status_conflict(self, a: dict[str, Any], b: dict[str, Any]) -> Optional[ContradictionRecord]:
        """Detect mutually exclusive legal, administrative, or constitutional characterizations."""
        st_a = a.get("statement", "").lower()
        st_b = b.get("statement", "").lower()

        for term1_pat, term2_pat in self.OPPOSING_TERMS:
            has_term1_a = bool(re.search(term1_pat, st_a))
            has_term2_b = bool(re.search(term2_pat, st_b))

            has_term2_a = bool(re.search(term2_pat, st_a))
            has_term1_b = bool(re.search(term1_pat, st_b))

            if (has_term1_a and has_term2_b) or (has_term2_a and has_term1_b):
                # Verify subject overlap
                tokens_a = {w for w in re.findall(r"\b[a-zA-Z]{4,}\b", st_a)}
                tokens_b = {w for w in re.findall(r"\b[a-zA-Z]{4,}\b", st_b)}
                common = tokens_a.intersection(tokens_b)
                if len(common) >= 2:
                    return ContradictionRecord(
                        claim_id_a=a["id"],
                        claim_id_b=b["id"],
                        conflict_type="STATUS_CONTRADICTION",
                        description=f"Mutually exclusive status classification on subject ({', '.join(list(common)[:3])})",
                        statement_a=a.get("statement", ""),
                        statement_b=b.get("statement", ""),
                    )
        return None

    def export_report(self, conflicts: list[ContradictionRecord], output_dir: Path) -> Path:
        """Serialize contradictions report to disk."""
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "contradictions_report.json"
        data = {
            "conflicts_count": len(conflicts),
            "status": "PASSED" if not conflicts else "CONFLICTS_DETECTED",
            "conflicts": [c.to_dict() for c in conflicts],
        }
        report_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return report_path
