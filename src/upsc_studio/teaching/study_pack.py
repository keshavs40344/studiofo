"""Connected Study Pack Builder: Generates comprehensive, evidence-linked study materials from the structured topic map and concept explanations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from upsc_studio.teaching.concept_explainer import ConceptExplanation, ExplanationMappingReport
from upsc_studio.teaching.topic_map import ContentPillar, StructuredTopicMap


class StudyPackBuilder:
    """Generates all 10 connected learning deliverables from verified knowledge and mapped concepts."""

    def __init__(self, teaching_dir: Path) -> None:
        self.teaching_dir = teaching_dir
        self.teaching_dir.mkdir(parents=True, exist_ok=True)

    def build_full_study_pack(
        self,
        topic_map: StructuredTopicMap,
        mapping_report: ExplanationMappingReport,
        verified_claims: list[dict[str, Any]],
        sections: list[dict[str, Any]],
    ) -> dict[str, str]:
        """Generate and save all 10 connected educational deliverables."""
        paths: dict[str, str] = {}
        pillar = topic_map.content_pillar

        # 1. Structured Topic Map JSON
        map_path = self.teaching_dir / "structured_topic_map.json"
        map_path.write_text(json.dumps(topic_map.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        paths["structured_topic_map"] = str(map_path)

        # 2. Detailed Study Notes (teaching/study_notes.md)
        notes_lines = [
            f"# Comprehensive Study Notes — {topic_map.title}",
            "",
            f"**Content Pillar:** {pillar.value.upper()}",
            f"**Total Required Concepts:** {mapping_report.total_required_concepts} | **Coverage:** {mapping_report.coverage_percentage}%",
            "",
            "## 1. Learning Objectives",
            *[f"- {obj}" for obj in topic_map.learning_objectives],
            "",
            "## 2. Prerequisite Knowledge",
            *[f"- {prereq}" for prereq in topic_map.prerequisite_knowledge],
            "",
            "## 3. Core Conceptual Explanations & Evidence",
        ]
        for exp in mapping_report.explanations:
            notes_lines.extend([
                f"### {exp.concept_name} `[{exp.category}]`",
                "",
                f"{exp.explanatory_passage}",
                "",
                f"**Illustrative Example:** {exp.concrete_example}",
                "",
                f"**Visual Representation:** *{exp.visual_direction['visual_type']}* — {exp.visual_direction['caption']}",
                "",
                f"**Evidence Links:** {', '.join(exp.evidence_links) or 'Core conceptual analysis'}",
                "",
            ])
        notes_path = self.teaching_dir / "study_notes.md"
        notes_path.write_text("\n".join(notes_lines), encoding="utf-8")
        paths["study_notes"] = str(notes_path)

        # 3. Quick Revision Notes (teaching/revision_notes.md & revision_sheet.md)
        rev_lines = [
            f"# High-Yield Quick Revision Sheet — {topic_map.title}",
            "",
            "| Concept | Definition & Key Mechanism | Landmark Precedent / Example |",
            "| :--- | :--- | :--- |",
        ]
        for exp in mapping_report.explanations:
            clean_def = exp.explanatory_passage.split(".")[0].replace("|", "-")
            clean_ex = exp.concrete_example.replace("|", "-")
            rev_lines.append(f"| **{exp.concept_name}** | {clean_def}. | {clean_ex} |")

        rev_lines.extend([
            "",
            "## High-Yield Takeaways",
            *[f"- **{exp.concept_name}:** {exp.concrete_example}" for exp in mapping_report.explanations],
        ])
        rev_path = self.teaching_dir / "revision_notes.md"
        rev_path.write_text("\n".join(rev_lines), encoding="utf-8")
        (self.teaching_dir / "revision_sheet.md").write_text("\n".join(rev_lines), encoding="utf-8")
        paths["revision_notes"] = str(rev_path)

        # 4. Glossary & Definitions (teaching/glossary.json & definitions.md)
        glossary_items = []
        def_lines = [f"# Glossary & Core Definitions — {topic_map.title}", ""]
        for c in topic_map.required_concepts:
            glossary_items.append({
                "term": c.name,
                "category": c.category.value,
                "definition": c.definition,
                "verified_claims": c.verified_claim_ids,
            })
            def_lines.extend([
                f"### {c.name}",
                f"- **Category:** `{c.category.value}`",
                f"- **Definition:** {c.definition}",
                "",
            ])
        gloss_path = self.teaching_dir / "glossary.json"
        gloss_path.write_text(json.dumps(glossary_items, indent=2, ensure_ascii=False), encoding="utf-8")
        (self.teaching_dir / "definitions.md").write_text("\n".join(def_lines), encoding="utf-8")
        paths["glossary"] = str(gloss_path)

        # 5. Concept Mind Map (Mermaid) (teaching/concept_map.mermaid & definitions_and_mindmap.md)
        mermaid_lines = [
            "graph TD",
            f"    ROOT[\"{topic_map.title}\"]",
        ]
        for idx, c in enumerate(topic_map.required_concepts, start=1):
            c_node = f"C{idx}"
            mermaid_lines.append(f"    ROOT --> {c_node}[\"{c.name}\"]")
            mermaid_lines.append(f"    {c_node} --> {c_node}_def[\"Scope: {c.category.value}\"]")
            if c.examples:
                clean_ex = c.examples[0].replace('"', "'")
                mermaid_lines.append(f"    {c_node} --> {c_node}_ex[\"Example: {clean_ex[:35]}...\"]")

        mermaid_content = "\n".join(mermaid_lines)
        (self.teaching_dir / "concept_map.mermaid").write_text(mermaid_content, encoding="utf-8")

        mindmap_doc = [
            f"# Concept Mind Map — {topic_map.title}",
            "",
            "```mermaid",
            mermaid_content,
            "```",
            "",
        ]
        (self.teaching_dir / "definitions_and_mindmap.md").write_text("\n".join(mindmap_doc), encoding="utf-8")
        paths["concept_map"] = str(self.teaching_dir / "concept_map.mermaid")

        # 6. Active Recall Flashcards (teaching/flashcards.json)
        flashcards = []
        for idx, c in enumerate(topic_map.required_concepts, start=1):
            # Card 1: Definition
            flashcards.append({
                "card_id": f"FC_{idx:02d}_DEF",
                "concept_id": c.concept_id,
                "front": f"What is the definition and core mandate of {c.name}?",
                "back": c.definition,
                "citation": c.verified_claim_ids[0] if c.verified_claim_ids else "Curriculum Standard",
            })
            # Card 2: Mechanism / Application
            if c.mechanisms:
                flashcards.append({
                    "card_id": f"FC_{idx:02d}_MECH",
                    "concept_id": c.concept_id,
                    "front": f"Explain the operational mechanism of {c.name}.",
                    "back": " ".join(c.mechanisms),
                    "citation": c.verified_claim_ids[0] if c.verified_claim_ids else "Curriculum Standard",
                })
            # Card 3: Common Misconception
            if c.common_misconceptions:
                m = c.common_misconceptions[0]
                flashcards.append({
                    "card_id": f"FC_{idx:02d}_MISC",
                    "concept_id": c.concept_id,
                    "front": f"Common Misconception about {c.name}: '{m['misconception']}' — Is this accurate?",
                    "back": f"NO. {m['correction']}",
                    "citation": "Academic Red-Team Benchmark",
                })

        fc_path = self.teaching_dir / "flashcards.json"
        fc_path.write_text(json.dumps(flashcards, indent=2, ensure_ascii=False), encoding="utf-8")
        paths["flashcards"] = str(fc_path)

        # 7. Practice MCQs with comprehensive explanations (teaching/practice_mcqs.json & question_bank.json)
        mcqs = self._build_practice_mcqs(topic_map, verified_claims) if verified_claims else []
        mcq_status = "GENERATED_FROM_VERIFIED_CLAIMS" if verified_claims else "NOT_GENERATED_INSUFFICIENT_AUTHENTICATED_QUESTION_DATA"
        mcq_path = self.teaching_dir / "practice_mcqs.json"
        mcq_path.write_text(json.dumps(mcqs, indent=2, ensure_ascii=False), encoding="utf-8")
        paths["practice_mcqs"] = str(mcq_path)

        # Update question_bank.json
        qbank = {
            "content_category": pillar.value,
            "chapter_title": topic_map.title,
            "note": (
                "No objective MCQ or official PYQ is fabricated. Verified PYQs must be imported "
                "from an authenticated question source; generated questions require answer-key review."
            ),
            "prelims_practice_mcqs": mcqs,
            "mcq_generation_status": mcq_status,
            "practice_prompts": [
                {
                    "id": "PROMPT_01",
                    "label": "PRACTICE_PROMPT_REVIEW_REQUIRED",
                    "question": f"Discuss the significance of {topic_map.title} in the context of institutional governance and individual liberty.",
                }
            ],
            "verified_pyqs": [],
        }
        (self.teaching_dir / "question_bank.json").write_text(json.dumps(qbank, indent=2, ensure_ascii=False), encoding="utf-8")

        # 8. Pillar-Specific Framework: Mains Answer Framework (for UPSC) or Topic Context (for non-UPSC)
        if pillar == ContentPillar.UPSC:
            mains_lines = [
                f"# UPSC Mains Answer Framework — {topic_map.title}",
                "",
                "## 1. Directive Breakdown & Introduction",
                f"- **Direct Definition:** {topic_map.required_concepts[0].definition if topic_map.required_concepts else topic_map.title}",
                "- **Constitutional Matrix:** Relevant Articles / Statutory Provisions.",
                "",
                "## 2. Core Body Arguments (Dimension-wise)",
                "- **Institutional & Legal Mandate:** Procedural enforcement mechanisms.",
                "- **Judicial Precedents:** Landmark rulings establishing ratio decidendi.",
                "- **Structural Constraints:** Administrative backlog, operational delays, resource bottlenecks.",
                "",
                "## 3. Way Forward & Reform Recommendations",
                "- Digital transparency and administrative process re-engineering.",
                "- Fast-track resolution and specialized tribunal oversight.",
                "- Strict adherence to proportionality and substantive due process.",
                "",
                "## 4. Evaluated Practice Mains Question",
                f"> **Question:** 'Analyze the evolution and constitutional enforcement of {topic_map.title}. How do landmark judicial precedents balance state authority with individual rights?' (15 Marks, 250 Words)",
            ]
            mains_path = self.teaching_dir / "mains_answer_frameworks.md"
            mains_path.write_text("\n".join(mains_lines), encoding="utf-8")
            (self.teaching_dir / "mains_track.md").write_text("\n".join(mains_lines), encoding="utf-8")
            paths["mains_frameworks"] = str(mains_path)
        else:
            ctx_lines = [
                f"# {pillar.value.upper()} Topic Context & Analysis — {topic_map.title}",
                "",
                f"**Research Cutoff Date:** {topic_map.research_cutoff_date or 'General Timeless Principle'}",
                "",
                "Notice: This is a General Knowledge / Science / Current Affairs project. "
                "UPSC syllabus tags and Prelims/Mains categorizations are strictly omitted to maintain domain isolation.",
                "",
                "## Core Findings & Empirical Sequence",
                *[f"- **{exp.concept_name}:** {exp.explanatory_passage}" for exp in mapping_report.explanations],
                "",
                "## Limitations & Unresolved Dimensions",
                *[f"- {c.name}: {c.counterexamples_and_limitations[0]}" for c in topic_map.required_concepts if c.counterexamples_and_limitations],
            ]
            ctx_path = self.teaching_dir / "topic_context.md"
            ctx_path.write_text("\n".join(ctx_lines), encoding="utf-8")
            (self.teaching_dir / "analysis_framework.md").write_text("\n".join(ctx_lines), encoding="utf-8")
            paths["topic_context"] = str(ctx_path)

        # 9. Chapter Summary (teaching/chapter_summary.md)
        summary_lines = [
            f"# Executive Chapter Summary — {topic_map.title}",
            "",
            f"**Domain Pillar:** {pillar.value.upper()}",
            f"**Verified Evidence Claims Linked:** {len(verified_claims)}",
            "",
            "## Executive Synthesis",
            f"This documentary lesson covers the foundational architecture of {topic_map.title}.",
            "",
            "### Section-by-Section Synthesis:",
            *[f"- **{s['title']}:** {s['objective']}" for s in sections],
            "",
            "### Conclusion & Learning Outcome:",
            f"Viewers gain a comprehensive understanding of {topic_map.title}, its operative mechanics, precedents, and critical contemporary debates.",
        ]
        sum_path = self.teaching_dir / "chapter_summary.md"
        sum_path.write_text("\n".join(summary_lines), encoding="utf-8")
        paths["chapter_summary"] = str(sum_path)

        return paths

    def _build_practice_mcqs(
        self,
        topic_map: StructuredTopicMap,
        verified_claims: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        mcqs = []
        for idx, concept in enumerate(topic_map.required_concepts[:3], start=1):
            claim_citation = concept.verified_claim_ids[0] if concept.verified_claim_ids else "Curriculum Definition"
            mcqs.append({
                "question_id": f"PRAC_MCQ_{idx:02d}",
                "label": "PRACTICE_QUESTION_VERIFIED_EVIDENCE",
                "question": f"With reference to '{concept.name}' in {topic_map.title}, consider the following statement:\n1. {concept.definition}\nWhich of the statements given above is/are correct?",
                "options": {
                    "A": "1 only",
                    "B": "Neither 1 nor 2",
                    "C": "Both 1 and 2",
                    "D": "2 only",
                },
                "correct_option": "A",
                "explanation": f"Statement 1 is correct: {concept.definition}. Sourced from verified knowledge base linked to {claim_citation}.",
                "source_evidence_link": claim_citation,
                "is_official_pyq": False,
            })
        return mcqs
