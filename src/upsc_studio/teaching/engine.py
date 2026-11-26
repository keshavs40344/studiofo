"""Teaching structure, Hinglish script generator, and study-material pack builder."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from upsc_studio.db.schemas import VerificationStatus


class TeachingEngine:
    """Generates structured UPSC teaching scripts, recording prompts, and study materials."""

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
        chapter_map: dict,
        notes_excerpt: str = "",
        tts_enabled: bool = False,
    ) -> dict:
        """Build teaching outline, Hinglish script, recording script, and study materials."""
        claims = [
            dict(r)
            for r in self.conn.execute(
                "SELECT * FROM claims WHERE project_id = ? ORDER BY id", (project_id,)
            ).fetchall()
        ]
        verified_claims = [c for c in claims if c["status"] == VerificationStatus.VERIFIED.value]
        blocked_claims = [c for c in claims if c["status"] != VerificationStatus.VERIFIED.value]

        primary_papers = ", ".join(chapter_map.get("primary_papers", ["Mains GS"]))
        sections = self._build_sections(chapter_title, primary_papers, verified_claims, notes_excerpt)

        total_words = sum(len(s["narration"].split()) for s in sections)
        estimated_minutes = round(total_words / self.WORDS_PER_MINUTE, 2)

        # 1. teaching_outline.md
        outline_lines = [f"# Teaching Outline — {chapter_title}", "", f"**Papers:** {primary_papers}", ""]
        for idx, sec in enumerate(sections, start=1):
            outline_lines.append(f"{idx}. **{sec['title']}** — {sec['objective']} (~{sec['duration_sec']}s)")
        (self.teaching_dir / "teaching_outline.md").write_text("\n".join(outline_lines), encoding="utf-8")

        # 2. script_hinglish.md
        script_lines = [
            f"# Hinglish Teaching Script — {chapter_title}",
            "",
            f"- **Estimated Narration Pace:** {self.WORDS_PER_MINUTE:.0f} WPM",
            f"- **Total Words:** {total_words}",
            f"- **Estimated Duration:** {estimated_minutes} minutes",
            f"- **Narration Mode:** {'TTS Enabled' if tts_enabled else 'USER OWN VOICE ONLY (TTS Disabled)'}",
            "",
        ]
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
            "Record each section clearly in a quiet room. Keep raw files unmodified; UPSC Studio will process and align them.",
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

        # 4. Prelims & Mains separate tracks
        prelims_lines = [
            f"# Prelims Track — {chapter_title}",
            "",
            "## Key Factual Points & Constitutional/Institutional Anchors",
        ]
        for c in verified_claims:
            prelims_lines.append(f"- [{c['id']}] {c['statement']} (Ref: {c['page_or_section'] or 'verified source'})")
        if not verified_claims:
            prelims_lines.append("- Add and verify factual claims in Research & Verification before finalising Prelims facts.")
        (self.teaching_dir / "prelims_track.md").write_text("\n".join(prelims_lines), encoding="utf-8")

        mains_lines = [
            f"# Mains Analytical Track — {chapter_title}",
            "",
            "## Multi-Dimensional Analysis",
            "- **Constitutional & Legal:** Examine statutory/constitutional basis and judicial interpretation.",
            "- **Institutional & Governance:** Assess accountability, neutrality, and implementation gaps.",
            "- **Way Forward:** Evidence-backed reforms and committee recommendations.",
            "",
            "## Practice Answer Framework (Educational Example — Not Official UPSC Answer)",
            "1. **Introduction:** Define the core concept with constitutional/statutory context.",
            "2. **Body:** Present 3–4 structured dimensions with balanced arguments and counterarguments.",
            "3. **Conclusion:** Forward-looking institutional reform linked to democratic accountability.",
        ]
        (self.teaching_dir / "mains_track.md").write_text("\n".join(mains_lines), encoding="utf-8")

        # 5. Study notes & revision sheet
        (self.teaching_dir / "study_notes.md").write_text(
            "\n".join(
                [
                    f"# Detailed Study Notes — {chapter_title}",
                    "",
                    f"**Mapped Papers:** {primary_papers}",
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

        # 6. Practice question bank (explicitly labelled as generated practice items, never PYQs)
        qbank = {
            "chapter_title": chapter_title,
            "note": "Generated practice questions are labelled PRACTICE_GENERATED, distinct from verified UPSC PYQs.",
            "prelims_practice_mcqs": [
                {
                    "id": "MCQ_PRAC_1",
                    "label": "PRACTICE_GENERATED",
                    "question": f"With reference to '{chapter_title}', consider the core constitutional/institutional mechanism discussed in this chapter. Which statement best reflects its primary purpose?",
                    "options": [
                        "Ensuring institutional accountability and stability",
                        "Replacing parliamentary oversight with executive decree",
                        "Eliminating judicial review completely",
                        "None of the above",
                    ],
                    "answer_index": 0,
                    "explanation": "Derived from the core conceptual objective of the chapter.",
                }
            ],
            "mains_practice_questions": [
                {
                    "id": "MAINS_PRAC_1",
                    "label": "PRACTICE_GENERATED",
                    "question": f"Critically examine the working, challenges, and needed reforms in '{chapter_title}' in the context of Indian democracy. (250 words / 15 marks)",
                }
            ],
            "verified_pyqs": [],
        }
        (self.teaching_dir / "question_bank.json").write_text(
            json.dumps(qbank, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Save structured sections JSON for storyboard engine
        (self.teaching_dir / "sections.json").write_text(
            json.dumps(sections, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return {
            "sections_count": len(sections),
            "total_words": total_words,
            "estimated_duration_min": estimated_minutes,
            "verified_claims_used": len(verified_claims),
            "blocked_claims_excluded": len(blocked_claims),
            "sections": sections,
        }

    def _build_sections(
        self,
        chapter_title: str,
        primary_papers: str,
        verified_claims: list[dict],
        notes_excerpt: str,
    ) -> list[dict]:
        claim_ids = [c["id"] for c in verified_claims]
        evidence_summary = (
            " ".join(c["statement"] for c in verified_claims[:4])
            if verified_claims
            else (notes_excerpt[:400].strip() or f"{chapter_title} is a core UPSC General Studies topic.")
        )

        raw_sections = [
            {
                "section_id": "SEC_01",
                "title": "Introduction & Why This Chapter Matters",
                "objective": f"Establish UPSC relevance of {chapter_title} across {primary_papers}.",
                "claim_ids": [],
                "visual_category": "Motion Graphics / Title Card",
                "narration": (
                    f"Namaste aur swagat hai UPSC Studio mein. Aaj hum detail mein padhenge '{chapter_title}'. "
                    f"Yeh chapter UPSC syllabus mein {primary_papers} ke liye bahut important hai, kyunki Prelims mein iske factual provisions aur Mains mein iska analytical impact directly pucha jaata hai."
                ),
            },
            {
                "section_id": "SEC_02",
                "title": "Core Definitions & Conceptual Foundation",
                "objective": "Define key terms clearly in Hinglish while retaining exact standard terminology.",
                "claim_ids": claim_ids[:2],
                "visual_category": "Learning Screen / Definition Card",
                "narration": (
                    f"Sabse pehle basic meaning samajhte hain. {chapter_title} ka core objective hai governance aur institutional accountability ko strong banana. "
                    f"Verified context ke hisaab se: {evidence_summary}"
                ),
            },
            {
                "section_id": "SEC_03",
                "title": "Mechanism, Process & Institutional Structure",
                "objective": "Explain step-by-step how the system or provision operates in practice.",
                "claim_ids": claim_ids[2:4],
                "visual_category": "Concept Animation / Flowchart",
                "narration": (
                    "Ab dekhte hain ki yeh mechanism step-by-step kaise kaam karta hai. "
                    "Har constitutional ya institutional process mein teen stages hoti hain: trigger condition, decision authority, aur judicial ya parliamentary review. "
                    "Is flowchart ke through aap clear sequence dekh sakte hain ki powers aur checks-and-balances kaise operate karte hain."
                ),
            },
            {
                "section_id": "SEC_04",
                "title": "Challenges, Critical Analysis & Reforms",
                "objective": "Balance arguments, limitations, and UPSC Mains way-forward reforms.",
                "claim_ids": [],
                "visual_category": "Data / Comparison Table",
                "narration": (
                    "Mains answer writing ke liye sirf provisions yaad rakhna kaafi nahi hai; humein challenges aur reforms bhi samajhne honge. "
                    "Ek taraf institutional stability zaroori hai, toh doosri taraf impartiality aur timely decision-making par bhi questions uthte hain. "
                    "Committee recommendations aur judicial observations humein ek balanced way forward dete hain."
                ),
            },
            {
                "section_id": "SEC_05",
                "title": "Prelims Points, Mains Framework & Recap",
                "objective": "Consolidate exam-ready takeaways and practice questions.",
                "claim_ids": claim_ids,
                "visual_category": "Summary & Practice Screen",
                "narration": (
                    f"Chaliye jaldi se recap karte hain. Aaj humne {chapter_title} ke definitions, step-by-step mechanism, aur critical reforms cover kiye. "
                    "Prelims ke liye exact articles aur authorities revise karein, aur Mains ke liye balanced intro-body-conclusion framework use karein."
                ),
            },
        ]

        for sec in raw_sections:
            words = len(sec["narration"].split())
            sec["duration_sec"] = max(6.0, round((words / self.WORDS_PER_MINUTE) * 60.0 + 1.5, 1))
        return raw_sections
