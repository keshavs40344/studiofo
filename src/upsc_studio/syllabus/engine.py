"""Versioned UPSC Syllabus loader, chapter mapper, and explanatory-depth coverage engine."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from upsc_studio.core.paths import DEFAULT_DATA_DIR
from upsc_studio.db.schemas import CoverageStatus


@dataclass
class CoverageEntry:
    syllabus_item_id: str
    stage: str
    paper: str
    topic: str
    subtopic: str
    relevance_score: int
    status: str
    reason: str
    matched_keywords: list[str]
    explanatory_signals: list[str]


class SyllabusEngine:
    """Maps chapters and notes to the official versioned UPSC syllabus."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        syllabus_json_path: Path | None = None,
    ) -> None:
        self.conn = conn
        self.syllabus_json_path = syllabus_json_path or (DEFAULT_DATA_DIR / "upsc_syllabus_v1.json")
        self.version = "unknown"
        self.source = ""
        self._load_and_seed()

    def _load_and_seed(self) -> None:
        data = json.loads(self.syllabus_json_path.read_text(encoding="utf-8"))
        self.version = data["version"]
        self.source = data["source"]
        for item in data["items"]:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO syllabus_items (
                    id, version, stage, paper, topic, subtopic, keywords_json, source_ref
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    self.version,
                    item["stage"],
                    item["paper"],
                    item["topic"],
                    item["subtopic"],
                    json.dumps(item["keywords"]),
                    self.source,
                ),
            )
        self.conn.commit()

    def list_items(self, stage: str | None = None) -> list[dict]:
        """Return syllabus items optionally filtered by stage (PRELIMS, MAINS, ESSAY, OPTIONAL)."""
        if stage:
            rows = self.conn.execute(
                "SELECT * FROM syllabus_items WHERE stage = ? ORDER BY id", (stage,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM syllabus_items ORDER BY id").fetchall()
        return [
            {
                "id": r["id"],
                "version": r["version"],
                "stage": r["stage"],
                "paper": r["paper"],
                "topic": r["topic"],
                "subtopic": r["subtopic"],
                "keywords": json.loads(r["keywords_json"]),
                "source_ref": r["source_ref"],
            }
            for r in rows
        ]

    def map_chapter(
        self,
        project_id: str,
        project_dir: Path,
        chapter_title: str,
        notes_text: str = "",
    ) -> dict:
        """Map chapter & notes to UPSC syllabus items and assess explanatory depth."""
        items = self.list_items()
        title_lower = chapter_title.lower()
        notes_lower = notes_text.lower()
        combined = f"{title_lower}\n{notes_lower}"

        # Guard: Never confuse Prelims CSAT with Mains GS-II
        is_csat_chapter = any(k in title_lower for k in ("csat", "numeracy", "comprehension", "syllogism", "data interpretation"))

        entries: list[CoverageEntry] = []
        for item in items:
            if item["paper"] == "Prelims CSAT Paper II" and not is_csat_chapter:
                continue
            if is_csat_chapter and item["paper"] != "Prelims CSAT Paper II":
                continue
            if item["stage"] in {"ESSAY", "OPTIONAL"} and item["stage"].lower() not in title_lower:
                continue

            kws = item["keywords"]
            title_hits = [kw for kw in kws if kw in title_lower]
            note_hits = [kw for kw in kws if kw in notes_lower]
            all_hits = sorted(set(title_hits + note_hits))

            if not all_hits:
                continue

            relevance = len(title_hits) * 3 + len(note_hits)
            signals = self._detect_explanatory_signals(notes_lower, all_hits)
            status, reason = self._classify_depth(notes_text, note_hits, signals)

            entries.append(
                CoverageEntry(
                    syllabus_item_id=item["id"],
                    stage=item["stage"],
                    paper=item["paper"],
                    topic=item["topic"],
                    subtopic=item["subtopic"],
                    relevance_score=relevance,
                    status=status.value,
                    reason=reason,
                    matched_keywords=all_hits,
                    explanatory_signals=signals,
                )
            )

        entries.sort(key=lambda e: e.relevance_score, reverse=True)
        if not entries:
            # Fallback: mark review required rather than silently dropping
            entries.append(
                CoverageEntry(
                    syllabus_item_id="MAINS_GS2_CONST",
                    stage="MAINS",
                    paper="Mains GS Paper II",
                    topic="Unmapped / Review Required",
                    subtopic="Manual syllabus mapping required for this chapter title",
                    relevance_score=0,
                    status=CoverageStatus.NEEDS_REVIEW.value,
                    reason="No automatic keyword/concept match found; human review required.",
                    matched_keywords=[],
                    explanatory_signals=[],
                )
            )

        self._persist_coverage(project_id, entries)
        syllabus_dir = project_dir / "syllabus"
        syllabus_dir.mkdir(parents=True, exist_ok=True)

        ordered_primary: list[str] = []
        for e in entries:
            if e.paper not in ordered_primary:
                ordered_primary.append(e.paper)
            if len(ordered_primary) >= 3:
                break

        chapter_map = {
            "project_id": project_id,
            "chapter_title": chapter_title,
            "syllabus_version": self.version,
            "syllabus_source": self.source,
            "primary_papers": ordered_primary,
            "prelims_dimensions": [asdict(e) for e in entries if e.stage == "PRELIMS"],
            "mains_dimensions": [asdict(e) for e in entries if e.stage == "MAINS"],
            "missing_or_partial_topics": [
                asdict(e) for e in entries if e.status in {CoverageStatus.MISSING.value, CoverageStatus.PARTIAL.value}
            ],
        }
        (syllabus_dir / "chapter_map.json").write_text(
            json.dumps(chapter_map, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (syllabus_dir / "coverage_matrix.json").write_text(
            json.dumps([asdict(e) for e in entries], indent=2, ensure_ascii=False), encoding="utf-8"
        )

        self._write_markdown_deliverables(syllabus_dir, chapter_title, entries)
        return chapter_map

    @staticmethod
    def _detect_explanatory_signals(notes_lower: str, keywords: list[str]) -> list[str]:
        """Check for actual explanation markers (not just isolated keyword mentions)."""
        signals: list[str] = []
        if not notes_lower.strip():
            return signals
        patterns = {
            "definition": r"\b(defined as|means|refers to|is a system|concept of)\b",
            "mechanism": r"\b(how it works|process|procedure|step|mechanism|provision|article|section)\b",
            "example": r"\b(for example|e\.g\.|case study|instance|such as)\b",
            "analysis": r"\b(challenge|limitation|criticism|significance|reform|advantage|disadvantage)\b",
        }
        for label, pat in patterns.items():
            if re.search(pat, notes_lower):
                signals.append(label)
        return signals

    @staticmethod
    def _classify_depth(
        notes_text: str, note_hits: list[str], signals: list[str]
    ) -> tuple[CoverageStatus, str]:
        if not notes_text.strip():
            return CoverageStatus.MISSING, "No user notes supplied yet; concept requires full explanation."
        if not note_hits:
            return CoverageStatus.MISSING, "Syllabus topic relevant to chapter title is absent from supplied notes."
        if len(signals) >= 3 and len(notes_text.split()) >= 80:
            return (
                CoverageStatus.COVERED,
                f"Explained with {', '.join(signals)} across {len(notes_text.split())} words.",
            )
        return (
            CoverageStatus.PARTIAL,
            f"Mentioned ({', '.join(note_hits)}), but lacks full explanatory depth (signals found: {signals or ['none']}).",
        )

    def _persist_coverage(self, project_id: str, entries: list[CoverageEntry]) -> None:
        self.conn.execute("DELETE FROM coverage_ledger WHERE project_id = ?", (project_id,))
        for e in entries:
            self.conn.execute(
                """
                INSERT INTO coverage_ledger (
                    id, project_id, syllabus_item_id, status, reason, note_refs_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"cov_{uuid.uuid4().hex[:10]}",
                    project_id,
                    e.syllabus_item_id,
                    e.status,
                    e.reason,
                    json.dumps(e.matched_keywords),
                ),
            )
        self.conn.commit()

    @staticmethod
    def _write_markdown_deliverables(
        syllabus_dir: Path, chapter_title: str, entries: list[CoverageEntry]
    ) -> None:
        obj_lines = [
            f"# Learning Objectives — {chapter_title}",
            "",
            "1. Understand foundational definitions, constitutional/institutional context, and rationale.",
            "2. Trace mechanisms, processes, and historical evolution accurately.",
            "3. Distinguish Prelims factual traps from Mains analytical dimensions.",
            "4. Evaluate limitations, real-world case studies, and evidence-backed reforms.",
            "",
            "## Mapped Syllabus Items",
        ]
        for e in entries:
            obj_lines.append(f"- **{e.paper} — {e.topic}**: {e.subtopic} (`{e.status}`)")
        (syllabus_dir / "learning_objectives.md").write_text("\n".join(obj_lines), encoding="utf-8")

        outline_lines = [
            f"# Chapter Outline — {chapter_title}",
            "",
            "1. Opening Context & Why This Chapter Matters",
            "2. UPSC Syllabus Connection (Prelims & Mains)",
            "3. Core Definitions & Foundational Principles",
            "4. Constitutional / Legal / Institutional Framework",
            "5. Step-by-Step Mechanism & Real-World Examples",
            "6. Challenges, Criticisms & Reforms",
            "7. Prelims Revision Points & Mains Answer Framework",
            "8. Recap & Practice Assessment",
        ]
        (syllabus_dir / "chapter_outline.md").write_text("\n".join(outline_lines), encoding="utf-8")
