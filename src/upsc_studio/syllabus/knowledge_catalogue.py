"""Persistent Channel Knowledge Catalogue: Tracks syllabus topic lifecycle and publication gates."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from upsc_studio.syllabus.knowledge_graph import KnowledgeGraph, KnowledgeNode


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CatalogueStatus(str, Enum):
    NOT_PLANNED = "NOT_PLANNED"
    RESEARCHING = "RESEARCHING"
    RESEARCH_VERIFIED = "RESEARCH_VERIFIED"
    SCRIPT_READY = "SCRIPT_READY"
    STORYBOARD_READY = "STORYBOARD_READY"
    VIDEO_RENDERED = "VIDEO_RENDERED"
    QA_PENDING = "QA_PENDING"
    QA_PASSED = "QA_PASSED"
    PUBLISHED = "PUBLISHED"
    NEEDS_REVISION = "NEEDS_REVISION"
    OUTDATED = "OUTDATED"


@dataclass
class TopicCatalogueEntry:
    node_id: str
    status: CatalogueStatus
    project_id: Optional[str] = None
    published_video_url: Optional[str] = None
    published_at: Optional[str] = None
    qa_passed_at: Optional[str] = None
    qa_report_id: Optional[str] = None
    notes: str = ""
    last_updated: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class KnowledgeCatalogue:
    """Channel-wide persistent topic completeness registry with rigorous publication validation."""

    def __init__(self, conn: sqlite3.Connection, graph: Optional[KnowledgeGraph] = None) -> None:
        self.conn = conn
        self.graph = graph or KnowledgeGraph()
        self._ensure_table()
        self._seed_untracked_nodes()

    def _ensure_table(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS channel_knowledge_catalogue (
                node_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                project_id TEXT,
                published_video_url TEXT,
                published_at TEXT,
                qa_passed_at TEXT,
                qa_report_id TEXT,
                notes TEXT NOT NULL DEFAULT '',
                last_updated TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def _seed_untracked_nodes(self) -> None:
        """Ensure all nodes from the knowledge graph exist in the catalogue."""
        now = utc_now_iso()
        existing = {
            r["node_id"]
            for r in self.conn.execute("SELECT node_id FROM channel_knowledge_catalogue").fetchall()
        }
        for node_id in self.graph.nodes:
            if node_id not in existing:
                self.conn.execute(
                    """
                    INSERT INTO channel_knowledge_catalogue (
                        node_id, status, project_id, published_video_url,
                        published_at, qa_passed_at, qa_report_id, notes, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node_id,
                        CatalogueStatus.NOT_PLANNED.value,
                        None,
                        None,
                        None,
                        None,
                        None,
                        "",
                        now,
                    ),
                )
        self.conn.commit()

    def get_entry(self, node_id: str) -> Optional[TopicCatalogueEntry]:
        row = self.conn.execute(
            "SELECT * FROM channel_knowledge_catalogue WHERE node_id = ?", (node_id,)
        ).fetchone()
        if not row:
            return None
        return TopicCatalogueEntry(
            node_id=row["node_id"],
            status=CatalogueStatus(row["status"]),
            project_id=row["project_id"],
            published_video_url=row["published_video_url"],
            published_at=row["published_at"],
            qa_passed_at=row["qa_passed_at"],
            qa_report_id=row["qa_report_id"],
            notes=row["notes"],
            last_updated=row["last_updated"],
        )

    def update_status(
        self,
        node_id: str,
        new_status: CatalogueStatus,
        project_id: Optional[str] = None,
        published_video_url: Optional[str] = None,
        qa_report_id: Optional[str] = None,
        qa_passed: bool = False,
        notes: str = "",
    ) -> TopicCatalogueEntry:
        """Update topic lifecycle status enforcing strict verification invariants."""
        if node_id not in self.graph.nodes:
            raise KeyError(f"Topic node '{node_id}' not found in UPSC knowledge graph.")

        now = utc_now_iso()
        entry = self.get_entry(node_id)
        if not entry:
            entry = TopicCatalogueEntry(node_id=node_id, status=CatalogueStatus.NOT_PLANNED)

        # -------------------------------------------------------------
        # INVARIANT 1: A topic CANNOT be marked PUBLISHED without a verified published URL
        # -------------------------------------------------------------
        if new_status == CatalogueStatus.PUBLISHED:
            url = published_video_url or entry.published_video_url
            if not url or not (url.startswith("http://") or url.startswith("https://")):
                raise ValueError(
                    f"Publication rejected for '{node_id}': A topic cannot be marked PUBLISHED without a verified URL."
                )
            entry.published_video_url = url
            entry.published_at = entry.published_at or now

        # -------------------------------------------------------------
        # INVARIANT 2: A topic CANNOT be marked QA_PASSED without passing all QA gates
        # -------------------------------------------------------------
        if new_status == CatalogueStatus.QA_PASSED:
            if not qa_passed and not entry.qa_passed_at:
                raise ValueError(
                    f"QA pass rejected for '{node_id}': All academic, visual, audio, subtitle, and technical gates must pass first."
                )
            entry.qa_passed_at = now
            if qa_report_id:
                entry.qa_report_id = qa_report_id

        entry.status = new_status
        if project_id:
            entry.project_id = project_id
        if qa_report_id:
            entry.qa_report_id = qa_report_id
        if notes:
            entry.notes = notes
        entry.last_updated = now

        self.conn.execute(
            """
            INSERT OR REPLACE INTO channel_knowledge_catalogue (
                node_id, status, project_id, published_video_url,
                published_at, qa_passed_at, qa_report_id, notes, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.node_id,
                entry.status.value,
                entry.project_id,
                entry.published_video_url,
                entry.published_at,
                entry.qa_passed_at,
                entry.qa_report_id,
                entry.notes,
                entry.last_updated,
            ),
        )
        self.conn.commit()
        return entry

    def get_catalogue_summary(self) -> dict[str, Any]:
        """Aggregate stats across total entries, statuses, papers, and subjects."""
        rows = self.conn.execute("SELECT * FROM channel_knowledge_catalogue").fetchall()
        total_entries = len(rows)

        by_status: dict[str, int] = {s.value: 0 for s in CatalogueStatus}
        published_count = 0
        qa_passed_count = 0
        video_rendered_count = 0
        script_ready_count = 0
        research_verified_count = 0

        for r in rows:
            st = r["status"]
            by_status[st] = by_status.get(st, 0) + 1
            if st == CatalogueStatus.PUBLISHED.value:
                published_count += 1
            if st in {CatalogueStatus.PUBLISHED.value, CatalogueStatus.QA_PASSED.value}:
                qa_passed_count += 1
            if st in {CatalogueStatus.PUBLISHED.value, CatalogueStatus.QA_PASSED.value, CatalogueStatus.QA_PENDING.value, CatalogueStatus.VIDEO_RENDERED.value}:
                video_rendered_count += 1
            if st in {CatalogueStatus.PUBLISHED.value, CatalogueStatus.QA_PASSED.value, CatalogueStatus.QA_PENDING.value, CatalogueStatus.VIDEO_RENDERED.value, CatalogueStatus.STORYBOARD_READY.value, CatalogueStatus.SCRIPT_READY.value}:
                script_ready_count += 1
            if st not in {CatalogueStatus.NOT_PLANNED.value, CatalogueStatus.RESEARCHING.value}:
                research_verified_count += 1

        # Breakdown by paper
        by_paper: dict[str, dict[str, Any]] = {}
        by_subject: dict[str, dict[str, Any]] = {}

        for r in rows:
            node = self.graph.get_node(r["node_id"])
            if not node:
                continue
            # Paper tracking
            p = node.paper
            if p not in by_paper:
                by_paper[p] = {"total": 0, "published": 0, "qa_passed": 0, "rendered": 0}
            by_paper[p]["total"] += 1
            if r["status"] == CatalogueStatus.PUBLISHED.value:
                by_paper[p]["published"] += 1
            if r["status"] in {CatalogueStatus.PUBLISHED.value, CatalogueStatus.QA_PASSED.value}:
                by_paper[p]["qa_passed"] += 1
            if r["status"] in {CatalogueStatus.PUBLISHED.value, CatalogueStatus.QA_PASSED.value, CatalogueStatus.VIDEO_RENDERED.value}:
                by_paper[p]["rendered"] += 1

            # Subject tracking
            sub = node.subject
            if sub not in by_subject:
                by_subject[sub] = {"total": 0, "published": 0, "qa_passed": 0, "rendered": 0}
            by_subject[sub]["total"] += 1
            if r["status"] == CatalogueStatus.PUBLISHED.value:
                by_subject[sub]["published"] += 1
            if r["status"] in {CatalogueStatus.PUBLISHED.value, CatalogueStatus.QA_PASSED.value}:
                by_subject[sub]["qa_passed"] += 1
            if r["status"] in {CatalogueStatus.PUBLISHED.value, CatalogueStatus.QA_PASSED.value, CatalogueStatus.VIDEO_RENDERED.value}:
                by_subject[sub]["rendered"] += 1

        missing = [
            r["node_id"]
            for r in rows
            if r["status"] in {CatalogueStatus.NOT_PLANNED.value, CatalogueStatus.RESEARCHING.value}
        ]
        needs_revision = [
            r["node_id"]
            for r in rows
            if r["status"] in {CatalogueStatus.NEEDS_REVISION.value, CatalogueStatus.OUTDATED.value}
        ]

        return {
            "total_entries": total_entries,
            "topics_researched": research_verified_count,
            "topics_with_scripts": script_ready_count,
            "topics_with_videos": video_rendered_count,
            "topics_qa_passed": qa_passed_count,
            "topics_published": published_count,
            "topics_missing_count": len(missing),
            "topics_requiring_update_count": len(needs_revision),
            "by_status": by_status,
            "by_paper": by_paper,
            "by_subject": by_subject,
            "missing_topic_ids": missing,
            "needs_revision_ids": needs_revision,
        }

    def list_topic_details(
        self,
        paper: Optional[str] = None,
        subject: Optional[str] = None,
        status: Optional[CatalogueStatus] = None,
    ) -> list[dict[str, Any]]:
        """Return enriched list of topic nodes with their catalogue status."""
        rows = self.conn.execute("SELECT * FROM channel_knowledge_catalogue").fetchall()
        status_map = {r["node_id"]: dict(r) for r in rows}

        results: list[dict[str, Any]] = []
        for node_id, node in self.graph.nodes.items():
            if paper and node.paper.lower() != paper.lower():
                continue
            if subject and node.subject.lower() != subject.lower():
                continue
            cat = status_map.get(node_id, {})
            current_status = cat.get("status", CatalogueStatus.NOT_PLANNED.value)
            if status and current_status != status.value:
                continue

            item = node.to_dict()
            item["catalogue_status"] = current_status
            item["published_video_url"] = cat.get("published_video_url")
            item["published_at"] = cat.get("published_at")
            item["qa_passed_at"] = cat.get("qa_passed_at")
            item["project_id"] = cat.get("project_id")
            item["notes"] = cat.get("notes", "")
            results.append(item)

        return results
