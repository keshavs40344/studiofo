"""Topic Completeness Auditor: Cross-layer verification across Coverage Matrix, Script, Storyboard, and Rendered Scenes."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from upsc_studio.universal.knowledge_mapper import ExplanationStatus, TopicCoverageItem, TopicKnowledgeMap


@dataclass
class ConceptExplanationAudit:
    item_id: str
    subtopic: str
    required_explanation: str
    status: ExplanationStatus
    found_in_script: bool
    explanation_depth_score: float   # 0.0 to 1.0
    matched_script_excerpts: list[str] = field(default_factory=list)
    found_in_visual: bool = False
    matched_scene_id: Optional[str] = None
    omission_reasons: list[str] = field(default_factory=list)


@dataclass
class TopicCompletenessReport:
    topic_title: str
    total_required_items: int
    fully_covered_items: int
    partially_covered_items: int
    missing_items: int
    unverified_items: int
    not_applicable_items: int
    actual_coverage_percentage: float
    is_approved: bool
    critical_omissions: list[str] = field(default_factory=list)
    item_audits: list[ConceptExplanationAudit] = field(default_factory=list)
    visual_script_mismatches: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_title": self.topic_title,
            "total_required_items": self.total_required_items,
            "fully_covered_items": self.fully_covered_items,
            "partially_covered_items": self.partially_covered_items,
            "missing_items": self.missing_items,
            "unverified_items": self.unverified_items,
            "not_applicable_items": self.not_applicable_items,
            "actual_coverage_percentage": round(self.actual_coverage_percentage, 1),
            "is_approved": self.is_approved,
            "critical_omissions": self.critical_omissions,
            "item_audits": [asdict(a) for a in self.item_audits],
            "visual_script_mismatches": self.visual_script_mismatches,
        }


class TopicCompletenessAuditor:
    """Verifies that every concept in the Topic Coverage Matrix is genuinely explained in script and visuals."""

    EXPLANATION_SIGNALS = [
        r"\b(defined as|means|refers to|is a|ka arth hai|ka matlab hai)\b",
        r"\b(how it works|process|mechanism|kaise kaam karta hai|prakriya|charan)\b",
        r"\b(for example|such as|instance|udaharan ke liye|jaise ki)\b",
        r"\b(because|leads to|results in|isliye|kyunki|parinaam)\b",
        r"\b(limitation|challenge|criticism|exception|apwaad|chunauti)\b",
    ]

    def audit_completeness(
        self,
        knowledge_map: TopicKnowledgeMap,
        script_text: str,
        storyboard_scenes: Optional[list[dict[str, Any]]] = None,
        rendered_scene_ids: Optional[list[str]] = None,
    ) -> TopicCompletenessReport:
        storyboard_scenes = storyboard_scenes or []
        rendered_scene_ids = set(rendered_scene_ids or [])

        script_lower = script_text.lower()
        item_audits: list[ConceptExplanationAudit] = []
        critical_omissions: list[str] = []
        visual_script_mismatches: list[str] = []

        fully_covered = 0
        partially_covered = 0
        missing = 0
        unverified = 0
        not_applicable = 0

        for item in knowledge_map.coverage_matrix:
            if item.explanation_status == ExplanationStatus.NOT_APPLICABLE:
                not_applicable += 1
                item_audits.append(
                    ConceptExplanationAudit(
                        item_id=item.item_id,
                        subtopic=item.subtopic,
                        required_explanation=item.required_explanation,
                        status=ExplanationStatus.NOT_APPLICABLE,
                        found_in_script=False,
                        explanation_depth_score=1.0,
                        omission_reasons=[f"Marked NOT_APPLICABLE: {item.na_reason or 'Documented exemption'}"],
                    )
                )
                continue

            # Tokenize required subtopic & explanation
            subtopic_tokens = set(re.findall(r"\w+", item.subtopic.lower()))
            explanation_tokens = set(re.findall(r"\w+", item.required_explanation.lower()))
            stop_words = {"the", "a", "an", "and", "or", "of", "to", "in", "is", "for", "with", "as", "by", "on"}
            meaningful_tokens = (subtopic_tokens | explanation_tokens) - stop_words

            # 1. Search script for mentions and explanations
            matches_count = sum(1 for tok in meaningful_tokens if tok in script_lower)
            token_ratio = (matches_count / len(meaningful_tokens)) if meaningful_tokens else 0.0

            # 2. Check for explanation signals (not just casual name-dropping)
            signals_found = 0
            for sig in self.EXPLANATION_SIGNALS:
                if re.search(sig, script_lower, re.IGNORECASE):
                    signals_found += 1

            depth_score = min(1.0, (token_ratio * 0.6) + (signals_found / len(self.EXPLANATION_SIGNALS) * 0.4))

            # 3. Check corresponding visual in storyboard
            scene_match: Optional[dict[str, Any]] = None
            found_in_visual = False
            for scn in storyboard_scenes:
                scn_text = f"{scn.get('title', '')} {scn.get('learning_objective', '')} {scn.get('visual_category', '')}".lower()
                if item.subtopic.lower() in scn_text or any(tok in scn_text for tok in list(meaningful_tokens)[:3]):
                    scene_match = scn
                    found_in_visual = True
                    break

            omissions: list[str] = []
            if token_ratio < 0.20:
                omissions.append(f"Subtopic '{item.subtopic}' is completely absent from the narration script.")
                status = ExplanationStatus.REQUIRED
                missing += 1
                if item.importance.value == "HIGH":
                    critical_omissions.append(f"HIGH IMPORTANCE OMISSION: '{item.subtopic}' has no explanation in script.")
            elif depth_score < 0.40:
                omissions.append(f"Subtopic '{item.subtopic}' is mentioned but lacks substantive pedagogical explanation (depth: {depth_score:.2f}).")
                status = ExplanationStatus.PARTIAL
                partially_covered += 1
                if item.importance.value == "HIGH":
                    critical_omissions.append(f"HIGH IMPORTANCE PARTIAL: '{item.subtopic}' lacks depth or practical mechanism.")
            else:
                status = ExplanationStatus.COVERED
                fully_covered += 1
                status = ExplanationStatus.COVERED
                fully_covered += 1

            # 4. Check for Visual-Script Mismatch
            if scene_match:
                scn_id = scene_match.get("scene_id", "")
                if rendered_scene_ids and scn_id not in rendered_scene_ids:
                    visual_script_mismatches.append(
                        f"Scene '{scn_id}' covering '{item.subtopic}' was planned in storyboard but missing from rendered video output."
                    )
            elif status == ExplanationStatus.COVERED and item.importance.value == "HIGH":
                visual_script_mismatches.append(
                    f"Subtopic '{item.subtopic}' is covered in narration but lacks a dedicated explanatory visual scene in the storyboard."
                )

            item_audits.append(
                ConceptExplanationAudit(
                    item_id=item.item_id,
                    subtopic=item.subtopic,
                    required_explanation=item.required_explanation,
                    status=status,
                    found_in_script=token_ratio >= 0.25,
                    explanation_depth_score=round(depth_score, 2),
                    found_in_visual=found_in_visual,
                    matched_scene_id=scene_match.get("scene_id") if scene_match else None,
                    omission_reasons=omissions,
                )
            )

        total_req = len(knowledge_map.coverage_matrix) - not_applicable
        actual_cov_pct = (fully_covered / total_req * 100.0) if total_req > 0 else 100.0
        is_approved = (len(critical_omissions) == 0 and actual_cov_pct >= 80.0)

        return TopicCompletenessReport(
            topic_title=knowledge_map.topic_title,
            total_required_items=total_req,
            fully_covered_items=fully_covered,
            partially_covered_items=partially_covered,
            missing_items=missing,
            unverified_items=unverified,
            not_applicable_items=not_applicable,
            actual_coverage_percentage=actual_cov_pct,
            is_approved=is_approved,
            critical_omissions=critical_omissions,
            item_audits=item_audits,
            visual_script_mismatches=visual_script_mismatches,
        )
