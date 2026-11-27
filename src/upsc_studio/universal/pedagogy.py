"""Pedagogy Engine: 18-step universal teaching progression with explicit requirement and reasoning tracking."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class PedagogicalStatus(str, Enum):
    REQUIRED = "REQUIRED"
    COVERED = "COVERED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NEEDS_RESEARCH = "NEEDS_RESEARCH"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass
class PedagogicalStep:
    step_number: int
    prompt_question: str
    dimension_name: str
    status: PedagogicalStatus = PedagogicalStatus.REQUIRED
    explanation_summary: str = ""
    not_applicable_reason: str = ""
    covered_in_scene: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


# The 18 Universal Pedagogical Questions
STANDARD_18_STEPS: list[tuple[int, str, str]] = [
    (1, "What is it?", "DEFINITION"),
    (2, "Why does it exist?", "TELEOLOGY_PURPOSE"),
    (3, "How did it originate?", "HISTORICAL_GENESIS"),
    (4, "What problem does it solve?", "PROBLEM_SOLVED"),
    (5, "How does it work?", "FUNCTIONAL_MECHANISM"),
    (6, "What are its components?", "STRUCTURAL_COMPONENTS"),
    (7, "What are its underlying principles?", "CORE_PRINCIPLES"),
    (8, "What happens step by step?", "PROCESS_SEQUENCE"),
    (9, "What is a practical example?", "PRACTICAL_EXAMPLE"),
    (10, "What are its real-world applications?", "REAL_WORLD_APPLICATION"),
    (11, "What are its advantages?", "BENEFITS_STRENGTHS"),
    (12, "What are its limitations?", "LIMITATIONS_BOTTLENECKS"),
    (13, "What are the common misconceptions?", "MISCONCEPTIONS"),
    (14, "What is its historical context?", "CONTEXTUAL_EVOLUTION"),
    (15, "What is its present relevance?", "CONTEMPORARY_RELEVANCE"),
    (16, "How does it connect with other concepts?", "INTERDISCIPLINARY_CONNECTIONS"),
    (17, "What are the important debates?", "CRITICAL_DEBATES"),
    (18, "What are the possible future implications?", "FUTURE_OUTLOOK"),
]


class UniversalPedagogyEngine:
    """Builds and audits the 18-step teaching progression for any domain topic."""

    def initialize_progression(self, topic_title: str, domain: str = "GENERAL") -> list[PedagogicalStep]:
        steps: list[PedagogicalStep] = []
        for num, question, dim in STANDARD_18_STEPS:
            steps.append(
                PedagogicalStep(
                    step_number=num,
                    prompt_question=question,
                    dimension_name=dim,
                    status=PedagogicalStatus.REQUIRED,
                    explanation_summary="",
                    not_applicable_reason="",
                )
            )
        return steps

    def mark_not_applicable(
        self,
        steps: list[PedagogicalStep],
        step_number: int,
        reason: str,
    ) -> PedagogicalStep:
        """Mark a pedagogical step NOT_APPLICABLE enforcing mandatory documented justification."""
        if not reason or len(reason.strip()) < 8:
            raise ValueError(
                f"Step {step_number} cannot be marked NOT_APPLICABLE without a recorded explanatory reason."
            )
        step = next((s for s in steps if s.step_number == step_number), None)
        if not step:
            raise KeyError(f"Step {step_number} not found.")

        step.status = PedagogicalStatus.NOT_APPLICABLE
        step.not_applicable_reason = reason.strip()
        return step

    def record_coverage(
        self,
        steps: list[PedagogicalStep],
        step_number: int,
        summary: str,
        scene_id: Optional[str] = None,
    ) -> PedagogicalStep:
        step = next((s for s in steps if s.step_number == step_number), None)
        if not step:
            raise KeyError(f"Step {step_number} not found.")

        step.status = PedagogicalStatus.COVERED
        step.explanation_summary = summary.strip()
        if scene_id:
            step.covered_in_scene = scene_id
        return step

    def audit_pedagogical_completeness(self, steps: list[PedagogicalStep]) -> dict[str, Any]:
        """Verify that all required steps are covered and any NOT_APPLICABLE steps have recorded reasons."""
        unresolved: list[int] = []
        covered: list[int] = []
        not_applicable: list[int] = []

        for s in steps:
            if s.status == PedagogicalStatus.COVERED:
                covered.append(s.step_number)
            elif s.status == PedagogicalStatus.NOT_APPLICABLE:
                if not s.not_applicable_reason:
                    unresolved.append(s.step_number)
                else:
                    not_applicable.append(s.step_number)
            else:
                unresolved.append(s.step_number)

        total = len(steps)
        effective_required = total - len(not_applicable)
        coverage_rate = (len(covered) / effective_required * 100.0) if effective_required > 0 else 100.0

        return {
            "total_steps": total,
            "covered_count": len(covered),
            "not_applicable_count": len(not_applicable),
            "unresolved_count": len(unresolved),
            "effective_coverage_rate": round(coverage_rate, 1),
            "unresolved_step_numbers": unresolved,
            "is_pedagogically_complete": len(unresolved) == 0,
        }
