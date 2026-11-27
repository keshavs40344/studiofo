"""Concept-to-Explanation Mapping System: Links each required concept to an explanatory passage, real example, visual direction, evidence, and coverage validation."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from upsc_studio.teaching.topic_map import ConceptCategory, StructuredTopicMap, TopicConcept


class ExplanationCoverage(str, Enum):
    COVERED = "COVERED"
    INCOMPLETE = "INCOMPLETE"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass
class ConceptExplanation:
    concept_id: str
    concept_name: str
    category: str
    explanatory_passage: str
    concrete_example: str
    visual_direction: dict[str, Any]
    evidence_links: list[str] = field(default_factory=list)
    coverage_status: ExplanationCoverage = ExplanationCoverage.COVERED
    validation_notes: list[str] = field(default_factory=list)
    word_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["coverage_status"] = self.coverage_status.value
        return d


@dataclass
class ExplanationMappingReport:
    topic_title: str
    content_pillar: str
    total_required_concepts: int
    covered_concepts_count: int
    incomplete_concepts_count: int
    unsupported_concepts_count: int
    coverage_percentage: float
    explanations: list[ConceptExplanation]
    validation_issues: list[str]
    is_pedagogically_complete: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_title": self.topic_title,
            "content_pillar": self.content_pillar,
            "total_required_concepts": self.total_required_concepts,
            "covered_concepts_count": self.covered_concepts_count,
            "incomplete_concepts_count": self.incomplete_concepts_count,
            "unsupported_concepts_count": self.unsupported_concepts_count,
            "coverage_percentage": self.coverage_percentage,
            "explanations": [e.to_dict() for e in self.explanations],
            "validation_issues": self.validation_issues,
            "is_pedagogically_complete": self.is_pedagogically_complete,
        }


class ConceptExplainerEngine:
    """Builds and validates concept-to-explanation mapping for every concept in the topic map."""

    # Keywords marking genuine explanatory depth
    MECHANISM_MARKERS = ["process", "mechanism", "procedure", "how it works", "sequence", "guarantees", "operates", "enforces", "steps"]
    EXAMPLE_MARKERS = ["for example", "e.g.", "case study", "instance", "such as", "landmark case", "precedent", "ruling"]
    ANALYSIS_MARKERS = ["significance", "limitation", "challenge", "criticism", "implication", "balance", "reform", "bottleneck"]

    def map_and_validate_concepts(
        self,
        topic_map: StructuredTopicMap,
        verified_claims: list[dict[str, Any]],
        notes_text: str = "",
    ) -> ExplanationMappingReport:
        claim_map = {str(c["id"]): c for c in verified_claims}
        explanations: list[ConceptExplanation] = []
        validation_issues: list[str] = []

        for concept in topic_map.required_concepts:
            exp = self._build_explanation(concept, claim_map, topic_map.title, notes_text)
            self._validate_explanation(concept, exp, validation_issues)
            explanations.append(exp)

        covered = sum(1 for e in explanations if e.coverage_status == ExplanationCoverage.COVERED)
        incomplete = sum(1 for e in explanations if e.coverage_status == ExplanationCoverage.INCOMPLETE)
        unsupported = sum(1 for e in explanations if e.coverage_status == ExplanationCoverage.UNSUPPORTED)
        total = len(explanations)
        pct = round((covered / total * 100.0), 1) if total > 0 else 0.0

        is_complete = (incomplete == 0 and unsupported == 0 and total > 0 and len(validation_issues) == 0)

        return ExplanationMappingReport(
            topic_title=topic_map.title,
            content_pillar=topic_map.content_pillar.value,
            total_required_concepts=total,
            covered_concepts_count=covered,
            incomplete_concepts_count=incomplete,
            unsupported_concepts_count=unsupported,
            coverage_percentage=pct,
            explanations=explanations,
            validation_issues=validation_issues,
            is_pedagogically_complete=is_complete,
        )

    def _build_explanation(
        self,
        concept: TopicConcept,
        claim_map: dict[str, dict[str, Any]],
        topic_title: str,
        notes_text: str,
    ) -> ConceptExplanation:
        # Find matching verified claims
        matched_claims = [claim_map[cid] for cid in concept.verified_claim_ids if cid in claim_map]
        claim_texts = [c["statement"] for c in matched_claims]

        # 1. Explanatory Passage
        passage_parts: list[str] = []
        passage_parts.append(f"{concept.name} is a fundamental pillar in understanding {topic_title}.")
        passage_parts.append(concept.definition)

        if concept.mechanisms:
            passage_parts.append(
                "Regarding its operational mechanism: " + " ".join(concept.mechanisms)
            )

        if claim_texts:
            passage_parts.append("Empirical and statutory evidence confirms: " + " ".join(claim_texts))

        passage = " ".join(passage_parts)

        # 2. Concrete Example
        example = concept.examples[0] if concept.examples else f"Representative application of {concept.name} in practice."

        # 3. Visual Direction
        v_type = "Diagram / Process Animation" if concept.category == ConceptCategory.MECHANISM else (
            "Comparative Split Screen" if concept.category == ConceptCategory.LIMITATION_COUNTEREXAMPLE else (
                "Historical Timeline / Milestone Map" if concept.category == ConceptCategory.HISTORICAL_DEVELOPMENT else "Definition Graphic / Title Card"
            )
        )
        visual_dir = {
            "visual_type": v_type,
            "on_screen_elements": [concept.name, concept.definition[:60] + "..."],
            "animation_dynamics": "Step-by-step element highlight synchronized with narration explanation.",
            "caption": f"Core Dimension: {concept.name}",
        }

        words = len(passage.split())

        # Initial coverage status
        status = ExplanationCoverage.COVERED
        notes: list[str] = []

        if not matched_claims and concept.category in (ConceptCategory.DEFINITION, ConceptCategory.MECHANISM):
            status = ExplanationCoverage.UNSUPPORTED
            notes.append("No verified evidence claims linked to this core concept.")
        elif words < 35:
            status = ExplanationCoverage.INCOMPLETE
            notes.append(f"Passage contains only {words} words; minimum 35 words required for conceptual depth.")

        return ConceptExplanation(
            concept_id=concept.concept_id,
            concept_name=concept.name,
            category=concept.category.value,
            explanatory_passage=passage,
            concrete_example=example,
            visual_direction=visual_dir,
            evidence_links=[c["id"] for c in matched_claims],
            coverage_status=status,
            validation_notes=notes,
            word_count=words,
        )

    def _validate_explanation(
        self,
        concept: TopicConcept,
        explanation: ConceptExplanation,
        issues: list[str],
    ) -> None:
        p_lower = explanation.explanatory_passage.lower()

        # Check for empty or invalid definition
        if not concept.definition or len(concept.definition.strip()) < 5:
            issues.append(f"Concept '{concept.name}' lacks a valid definition.")
            explanation.coverage_status = ExplanationCoverage.INCOMPLETE

        # Check for empty or missing explanatory passage
        if not explanation.explanatory_passage.strip():
            issues.append(f"Concept '{concept.name}' lacks an explanatory passage.")
            explanation.coverage_status = ExplanationCoverage.INCOMPLETE
            return

        # Check for shallow keyword-only mention (must explain mechanism or meaning)
        has_mechanism = any(m in p_lower for m in self.MECHANISM_MARKERS)
        if not has_mechanism and concept.category == ConceptCategory.MECHANISM:
            issues.append(f"Concept '{concept.name}' lacks a functional mechanism explanation.")
            explanation.coverage_status = ExplanationCoverage.INCOMPLETE

        # Check for concrete example
        if not explanation.concrete_example.strip():
            issues.append(f"Concept '{concept.name}' lacks an illustrative example.")
            explanation.coverage_status = ExplanationCoverage.INCOMPLETE

        # Check for unsupported claims in factual categories
        if concept.category in (ConceptCategory.DEFINITION, ConceptCategory.MECHANISM) and not explanation.evidence_links:
            issues.append(f"Concept '{concept.name}' is in category '{concept.category.value}' but has no verified evidence claims.")
            explanation.coverage_status = ExplanationCoverage.UNSUPPORTED
