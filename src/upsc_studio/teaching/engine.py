"""Teaching structure, Hinglish script generator, and study-material pack builder."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from upsc_studio.db.schemas import VerificationStatus
from upsc_studio.teaching.concept_explainer import ConceptExplainerEngine
from upsc_studio.teaching.study_pack import StudyPackBuilder
from upsc_studio.teaching.topic_map import ContentPillar, TopicMapBuilder


class TeachingEngine:
    """Builds UPSC teaching materials from claims explicitly marked VERIFIED.

    Unverified statements are excluded. Duration shortfalls are reported rather than
    filled with invented historical, legal, statistical, or institutional details.
    """

    WORDS_PER_MINUTE = 130.0  # Measured comfortable Hinglish teaching pace

    def __init__(self, conn: sqlite3.Connection, project_dir: Path) -> None:
        self.conn = conn
        self.project_dir = project_dir
        self.teaching_dir = project_dir / "teaching"
        self.teaching_dir.mkdir(parents=True, exist_ok=True)

    def generate_teaching_package(
        self,
        project_id: str,
        chapter_title: str,
        chapter_map: dict[str, Any],
        notes_excerpt: str = "",
        tts_enabled: bool = False,
        target_duration_min: int = 5,
        content_category: str = "upsc",
    ) -> dict[str, Any]:
        """Build teaching outline, Hinglish script, recording script, and study materials."""
        claims = [
            dict(r)
            for r in self.conn.execute(
                "SELECT * FROM claims WHERE project_id = ? ORDER BY id", (project_id,)
            ).fetchall()
        ]
        verified_claims = [c for c in claims if c["status"] == VerificationStatus.VERIFIED.value]
        blocked_claims = [c for c in claims if c["status"] != VerificationStatus.VERIFIED.value]

        category_labels = {
            "upsc": "UPSC syllabus",
            "general_knowledge": "General Knowledge",
            "current_affairs": "Current Affairs",
            "deep_dive": "Deep Dive",
        }
        if content_category not in category_labels:
            raise ValueError(f"Unsupported content category: {content_category}")
        papers_or_category = chapter_map.get("primary_papers") or [category_labels[content_category]]
        primary_papers = ", ".join(papers_or_category)

        cutoff_date = chapter_map.get("research_cutoff_date")
        topic_map = TopicMapBuilder().build_topic_map(
            topic_title=chapter_title,
            content_category=content_category,
            verified_claims=verified_claims,
            cutoff_date=cutoff_date,
        )
        mapping_report = ConceptExplainerEngine().map_and_validate_concepts(
            topic_map=topic_map,
            verified_claims=verified_claims,
            notes_text=notes_excerpt,
        )

        sections = self._build_sections(
            chapter_title=chapter_title,
            primary_papers=primary_papers,
            verified_claims=verified_claims,
            notes_excerpt=notes_excerpt,
            target_duration_min=target_duration_min,
        )

        total_words = sum(len(s["narration"].split()) for s in sections)
        estimated_minutes = round(total_words / self.WORDS_PER_MINUTE, 2)

        # 1. teaching_outline.md
        outline_lines = [f"# Teaching Outline — {chapter_title}", "", f"**Category / Syllabus Context:** {primary_papers}", ""]
        for idx, sec in enumerate(sections, start=1):
            outline_lines.append(f"{idx}. **{sec['title']}** — {sec['objective']} (~{sec['duration_sec']}s)")
        (self.teaching_dir / "teaching_outline.md").write_text("\n".join(outline_lines), encoding="utf-8")

        # 2. script_hinglish.md
        script_lines = [
            f"# Hinglish Teaching Script — {chapter_title}",
            f"**Content Category:** {category_labels[content_category]}",

            "",
            f"- **Target Duration:** {target_duration_min} minutes",
            f"- **Estimated Narration Pace:** {self.WORDS_PER_MINUTE:.0f} WPM",
            f"- **Total Words:** {total_words}",
            f"- **Estimated Duration:** {estimated_minutes} minutes",
            f"- **Narration Mode:** {'TTS Enabled' if tts_enabled else 'USER OWN VOICE ONLY (TTS Disabled)'}",
            f"- **Evidence Status:** {len(verified_claims)} VERIFIED claim(s); {len(blocked_claims)} excluded claim(s)",
            f"- **Content Readiness:** {'READY_FOR_HUMAN_REVIEW' if verified_claims and not blocked_claims else 'INSUFFICIENT_EVIDENCE'}",
            "",
        ]
        if not verified_claims or blocked_claims:
            script_lines.extend([
                "> **Release restriction:** This is a draft. Insufficient or unverified evidence remains. Do not treat it as a fact-checked lesson or publish it.",
                "",
            ])
        if blocked_claims:
            script_lines.append(
                f"> **Notice:** {len(blocked_claims)} unverified/pending claim(s) were excluded from final narration and logged in `research/unresolved_claims.md`."
            )
            script_lines.append("")

        for sec in sections:
            script_lines.extend(
                [
                    f"## [{sec['section_id']}] {sec['title']}",
                    f"*Objective:* {sec['objective']} | *Claims:* {', '.join(sec['claim_ids']) or 'Conceptual'}",
                    "",
                    sec["narration"],
                    "",
                ]
            )
        (self.teaching_dir / "script_hinglish.md").write_text("\n".join(script_lines), encoding="utf-8")

        # 3. recording_script.md (Section-wise checklist for user's own voice)
        rec_lines = [
            f"# Own-Voice Recording Script — {chapter_title}",
            "",
            "Record only after checking the evidence status above. This draft contains only claims marked VERIFIED; placeholders mean insufficient information. Keep the raw recording unmodified.",
            "",
        ]
        for sec in sections:
            rec_lines.extend(
                [
                    f"### [ ] {sec['section_id']} — {sec['title']} (~{sec['duration_sec']}s)",
                    "",
                    sec["narration"],
                    "",
                    "---",
                    "",
                ]
            )
        (self.teaching_dir / "recording_script.md").write_text("\n".join(rec_lines), encoding="utf-8")

        # 4. Category-specific learning tracks
        if content_category == "upsc":
            prelims_lines = [
                f"# Prelims Track — {chapter_title}",
                "",
                "## Source-Backed Factual Points (Only Claims Marked VERIFIED)",
            ]
            for claim in verified_claims:
                prelims_lines.append(
                    f"- [{claim['id']}] {claim['statement']} (Ref: {claim['page_or_section'] or 'verified source'})"
                )
            if not verified_claims:
                prelims_lines.append("- Insufficient information: add and verify factual claims before finalising.")
            (self.teaching_dir / "prelims_track.md").write_text(
                "\n".join(prelims_lines), encoding="utf-8"
            )

            mains_lines = [
                f"# Mains Analytical Track — {chapter_title}",
                "",
                "## Evidence-Led Answer Framework",
                "- **Definition and scope:** Use a source-backed definition; do not infer missing details.",
                "- **Context and mechanism:** Include only steps and institutions directly supported by reviewed sources.",
                "- **Implications and debates:** Separate sourced facts from analysis; cite each factual example.",
                "- **Limitations and reforms:** Include cases, committees, and recommendations only when independently sourced and verified.",
                "",
                "## Practice Answer Structure (Framework, Not a Model Answer)",
                "1. **Introduction:** Define the topic using verified material.",
                "2. **Body:** Organise available evidence into relevant dimensions; label evidence gaps.",
                "3. **Conclusion:** Summarise supported findings without inventing a recommendation.",
            ]
            (self.teaching_dir / "mains_track.md").write_text(
                "\n".join(mains_lines), encoding="utf-8"
            )
        else:
            topic_context = [
                f"# {category_labels[content_category]} Topic Context — {chapter_title}",
                "",
                f"**Research cutoff:** {chapter_map.get('research_cutoff_date') or 'Not applicable'}",
                "",
                "Only statements linked to claims marked VERIFIED are included in the factual lesson.",
                "This category does not use UPSC Prelims/Mains syllabus tracks.",
                "",
                *[
                    f"- [{claim['id']}] {claim['statement']} (Ref: {claim['page_or_section'] or 'verified source'})"
                    for claim in verified_claims
                ],
            ]
            if not verified_claims:
                topic_context.append("- Insufficient information: no verified factual claims are available.")
            (self.teaching_dir / "topic_context.md").write_text(
                "\n".join(topic_context), encoding="utf-8"
            )
            analysis_framework = [
                f"# Analysis Framework — {chapter_title}",
                "",
                "This is a neutral organising framework, not evidence that each dimension applies.",
                "1. Definitions and scope (source required).",
                "2. Historical / institutional context (only where sourced).",
                "3. Evidence, data and examples (cite and date each item).",
                "4. Competing interpretations and limitations (source both sides).",
                "5. Open questions and unresolved evidence gaps.",
            ]
            (self.teaching_dir / "analysis_framework.md").write_text(
                "\n".join(analysis_framework), encoding="utf-8"
            )

        # 5. Study notes & revision sheet
        (self.teaching_dir / "study_notes.md").write_text(
            "\n".join(
                [
                    f"# Detailed Study Notes — {chapter_title}",
                    "",
                    f"**Category / Syllabus Context:** {primary_papers}",
                    "",
                    *[f"### {s['title']}\n\n{s['narration']}\n" for s in sections],
                ]
            ),
            encoding="utf-8",
        )
        (self.teaching_dir / "revision_sheet.md").write_text(
            "\n".join(
                [
                    f"# Quick Revision Sheet — {chapter_title}",
                    "",
                    *[f"- **{s['title']}:** {s['objective']}" for s in sections],
                ]
            ),
            encoding="utf-8",
        )

        # Definitions and concept mind map
        mindmap_lines = [
            f"# Evidence-Led Concept Map — {chapter_title}",
            "",
            "> The branches below are an organising framework, not claims that each dimension applies to this topic.",
            "",
            "```mermaid",
            "graph TD",
            f"    A[\"{chapter_title}\"] --> B[\"Definitions and Scope\"]",
            f"    A --> C[\"Source-Backed Concepts\"]",
            f"    A --> D[\"Processes (Only If Sourced)\"]",
            f"    A --> E[\"Implications and Open Questions\"]",
            "```",
            "",
        ]
        (self.teaching_dir / "definitions_and_mindmap.md").write_text("\n".join(mindmap_lines), encoding="utf-8")

        # 6. Practice question bank (explicitly labelled as generated practice items, never PYQs)
        if content_category == "upsc":
            practice_questions = [
                {
                    "id": "MAINS_PROMPT_1",
                    "label": "PRACTICE_PROMPT_REVIEW_REQUIRED",
                    "question": (
                        f"Explain '{chapter_title}' using only the verified source-backed points "
                        "in this chapter. Identify any unresolved evidence gaps."
                    ),
                }
            ]
        else:
            practice_questions = [
                {
                    "id": "DISCUSSION_PROMPT_1",
                    "label": "PRACTICE_PROMPT_REVIEW_REQUIRED",
                    "question": (
                        f"Summarise the source-backed findings on '{chapter_title}', distinguish "
                        "facts from interpretation, and list unresolved evidence gaps."
                    ),
                }
            ]
        qbank = {
            "content_category": content_category,
            "chapter_title": chapter_title,
            "note": (
                "No objective MCQ or official PYQ is fabricated. Verified PYQs must be imported "
                "from an authenticated question source; generated questions require answer-key review."
            ),
            "prelims_practice_mcqs": [],
            "mcq_generation_status": "NOT_GENERATED_INSUFFICIENT_AUTHENTICATED_QUESTION_DATA",
            "practice_prompts": practice_questions,
            "verified_pyqs": [],
        }
        (self.teaching_dir / "question_bank.json").write_text(
            json.dumps(qbank, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Save structured sections JSON for storyboard engine
        (self.teaching_dir / "sections.json").write_text(
            json.dumps(sections, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Generate connected learning deliverables pack
        pack_builder = StudyPackBuilder(self.teaching_dir)
        study_pack_paths = pack_builder.build_full_study_pack(
            topic_map=topic_map,
            mapping_report=mapping_report,
            verified_claims=verified_claims,
            sections=sections,
        )

        return {
            "content_category": content_category,
            "sections_count": len(sections),
            "total_words": total_words,
            "estimated_duration_min": estimated_minutes,
            "verified_claims_used": len(verified_claims),
            "blocked_claims_excluded": len(blocked_claims),
            "content_readiness": (
                "READY_FOR_HUMAN_REVIEW" if verified_claims and not blocked_claims
                else "INSUFFICIENT_EVIDENCE"
            ),
            "sections": sections,
            "topic_map": topic_map.to_dict(),
            "explanation_mapping": mapping_report.to_dict(),
            "study_pack": study_pack_paths,
        }

    def _build_sections(
        self,
        chapter_title: str,
        primary_papers: str,
        verified_claims: list[dict[str, Any]],
        notes_excerpt: str,
        target_duration_min: int = 5,
    ) -> list[dict[str, Any]]:
        """Create natural Hinglish narration from ALL explicitly verified claim text.

        Every verified claim is included across the core teaching sections so no
        exam-relevant fact is dropped. If no verified claims exist, reports
        insufficient evidence without fabricating facts.
        """
        del notes_excerpt, target_duration_min
        claim_ids = [str(item["id"]) for item in verified_claims]

        def claim_block(items: list[dict[str, Any]], heading: str) -> str:
            if not items:
                return (
                    f"{heading}\n"
                    "Insufficient information: no matching source-backed claim is marked VERIFIED. "
                    "Add and review suitable sources before recording this section."
                )
            spoken_sentences = [heading]
            for item in items:
                stmt = str(item["statement"]).strip()
                if stmt and not stmt.endswith((".", "!", "?", "।")):
                    stmt += "."
                spoken_sentences.append(stmt)
            return "\n".join(spoken_sentences)

        # Distribute ALL verified claims evenly across the 3 core teaching sections
        # so nothing is truncated when chapters have 20-50+ verified facts.
        n = len(verified_claims)
        if n == 0:
            first, middle, later = [], [], []
        elif n <= 3:
            first, middle, later = verified_claims, [], []
        else:
            c1 = max(1, (n + 2) // 3)
            c2 = max(c1 + 1, (2 * n + 2) // 3)
            first = verified_claims[:c1]
            middle = verified_claims[c1:c2]
            later = verified_claims[c2:]

        if verified_claims:
            recap_text = (
                f"Toh doston, '{chapter_title}' ke is complete revision mein humne kul {n} verified facts aur concepts cover kiye hain. "
                "Prelims aur Mains dono ke liye in saare dates, sites, personalities aur institutional facts ko revise karein. "
                + " ".join(str(item["statement"]).strip().rstrip(".") + "." for item in verified_claims[:4])
            )
        else:
            recap_text = claim_block(verified_claims, "Verified source-backed points for revision:")

        raw_sections = [
            {
                "section_id": "SEC_01",
                "title": "Introduction, Scope & Learning Objectives",
                "objective": f"Introduce {chapter_title} and define the scope of this lesson without adding unsourced facts.",
                "claim_ids": [],
                "visual_category": "Motion Graphics / Title Card",
                "narration": (
                    f"Namaste aur swagat hai UPSC Studio mein. Aaj hum '{chapter_title}' ko "
                    "poori gehraai aur source-led tareeke se samjhenge. Is lesson mein har factual statement "
                    "verified official aur academic sources par aadharit hai. "
                    f"Subject context: {primary_papers}."
                ),
            },
            {
                "section_id": "SEC_02",
                "title": "Definition, Core Concepts & Historical Context",
                "objective": "Present reviewed definitions, chronology, and foundational verified facts.",
                "claim_ids": [str(item["id"]) for item in first],
                "visual_category": "Learning Screen / Definition Card",
                "narration": claim_block(
                    first,
                    f"Aaiye '{chapter_title}' ke foundational concepts aur core facts ko samajhte hain:",
                ),
            },
            {
                "section_id": "SEC_03",
                "title": "Structure, Mechanism & Key Features",
                "objective": "Describe mechanisms, architecture, economy, and verified structural details.",
                "claim_ids": [str(item["id"]) for item in middle],
                "visual_category": "Concept Animation / Flowchart",
                "narration": claim_block(
                    middle,
                    f"Ab '{chapter_title}' ke key features, structure aur working mechanism ko detail mein dekhte hain:",
                ),
            },
            {
                "section_id": "SEC_04",
                "title": "Implications, Debates & Analytical Dimensions",
                "objective": "Present analytical dimensions, cultural/scientific legacy, and scholarly debates.",
                "claim_ids": [str(item["id"]) for item in later],
                "visual_category": "Data / Comparison Table",
                "narration": claim_block(
                    later,
                    f"Ab aaiye '{chapter_title}' ke analytical dimensions, debates aur major findings ko samajhte hain:",
                ),
            },
            {
                "section_id": "SEC_05",
                "title": "Revision, Exam Framework & Key Takeaways",
                "objective": "Recap verified material for Prelims & Mains and highlight exam-critical takeaways.",
                "claim_ids": claim_ids,
                "visual_category": "Summary & Practice Screen",
                "narration": recap_text,
            },
        ]

        for section in raw_sections:
            word_count = len(section["narration"].split())
            section["duration_sec"] = max(
                6.0,
                round((word_count / self.WORDS_PER_MINUTE) * 60.0 + 1.5, 1),
            )

        return raw_sections
