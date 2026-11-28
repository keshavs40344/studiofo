"""Structured research planning for evidence-driven educational documentaries.

Identifies required research dimensions, primary source requirements,
target search queries, and corroboration thresholds prior to source ingestion.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class ResearchDimension(str, Enum):
    CONSTITUTIONAL_STATUTORY = "CONSTITUTIONAL_STATUTORY"
    JUDICIAL_PRECEDENTS = "JUDICIAL_PRECEDENTS"
    STATISTICAL_EMPIRICAL = "STATISTICAL_EMPIRICAL"
    INSTITUTIONAL_FRAMEWORK = "INSTITUTIONAL_FRAMEWORK"
    CURRENT_AFFAIRS_POLICY = "CURRENT_AFFAIRS_POLICY"
    HISTORICAL_EVOLUTION = "HISTORICAL_EVOLUTION"


@dataclass
class ResearchPriority:
    dimension: ResearchDimension
    topic_focus: str
    target_queries: list[str]
    mandatory_source_tier: str  # PRIMARY_OFFICIAL, ACADEMIC_PEER_REVIEWED, REPUTABLE_NEWS
    min_corroborating_sources: int = 1
    temporal_cutoff: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["dimension"] = self.dimension.value
        return d


@dataclass
class ResearchPlan:
    project_id: str
    topic_title: str
    content_category: str
    cutoff_date: Optional[str]
    priorities: list[ResearchPriority] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "topic_title": self.topic_title,
            "content_category": self.content_category,
            "cutoff_date": self.cutoff_date,
            "priorities_count": len(self.priorities),
            "priorities": [p.to_dict() for p in self.priorities],
        }

    def save(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / "research_plan.json"
        file_path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return file_path


class ResearchPlanner:
    """Generates structured research plans based on topic and syllabus parameters."""

    def build_plan(
        self,
        project_id: str,
        topic_title: str,
        content_category: str = "upsc",
        cutoff_date: Optional[str] = None,
        key_concepts: Optional[list[str]] = None,
    ) -> ResearchPlan:
        """Construct a structured research plan spanning essential analytical dimensions."""
        priorities: list[ResearchPriority] = []
        concepts = key_concepts or [topic_title]

        # 1. Constitutional & Statutory Dimension (for UPSC and legal/governance topics)
        if content_category in {"upsc", "deep_dive"}:
            priorities.append(
                ResearchPriority(
                    dimension=ResearchDimension.CONSTITUTIONAL_STATUTORY,
                    topic_focus=f"{topic_title}: Constitutional provisions, statutes, and schedules",
                    target_queries=[
                        f"{topic_title} Constitution of India official bare text",
                        f"{topic_title} bare act Ministry of Law and Justice",
                        f"{topic_title} statutory authority gazette notification",
                    ],
                    mandatory_source_tier="PRIMARY_OFFICIAL",
                    min_corroborating_sources=1,
                    temporal_cutoff=cutoff_date,
                    notes="Requires official gazette, bare act, or Constitutional text. Coaching notes unacceptable.",
                )
            )

            priorities.append(
                ResearchPriority(
                    dimension=ResearchDimension.JUDICIAL_PRECEDENTS,
                    topic_focus=f"{topic_title}: Landmark Supreme Court judgments and legal doctrine",
                    target_queries=[
                        f"{topic_title} Supreme Court landmark judgments Indian Kanoon",
                        f"{topic_title} constitutional bench ratio decidendi",
                    ],
                    mandatory_source_tier="PRIMARY_OFFICIAL",
                    min_corroborating_sources=1,
                    temporal_cutoff=cutoff_date,
                    notes="Must cite actual case name, year, and ratio. Do not fabricate rulings.",
                )
            )

        # 2. Institutional Framework & Mechanisms
        priorities.append(
            ResearchPriority(
                dimension=ResearchDimension.INSTITUTIONAL_FRAMEWORK,
                topic_focus=f"{topic_title}: Institutional mechanisms, procedures, and oversight bodies",
                target_queries=[
                    f"{topic_title} nodal ministry executive mandate",
                    f"{topic_title} statutory commission annual report",
                ],
                mandatory_source_tier="PRIMARY_OFFICIAL",
                min_corroborating_sources=1,
                temporal_cutoff=cutoff_date,
                notes="Identify statutory vs constitutional status, composition, and removal procedures.",
            )
        )

        # 3. Statistical & Empirical Dimension
        priorities.append(
            ResearchPriority(
                dimension=ResearchDimension.STATISTICAL_EMPIRICAL,
                topic_focus=f"{topic_title}: Empirical indicators, survey metrics, and administrative data",
                target_queries=[
                    f"{topic_title} MoSPI official statistical report",
                    f"{topic_title} NITI Aayog index economic survey data",
                ],
                mandatory_source_tier="PRIMARY_OFFICIAL",
                min_corroborating_sources=2,
                temporal_cutoff=cutoff_date,
                notes="Quantitative claims require 2 independent sources or primary government release with exact reference year.",
            )
        )

        # 4. Current Affairs & Policy Developments (Strict Cutoff)
        if content_category in {"upsc", "current_affairs"}:
            priorities.append(
                ResearchPriority(
                    dimension=ResearchDimension.CURRENT_AFFAIRS_POLICY,
                    topic_focus=f"{topic_title}: Contemporary policy reforms, committee reports, and recent developments",
                    target_queries=[
                        f"{topic_title} government committee recommendations PIB",
                        f"{topic_title} parliamentary committee report summary",
                    ],
                    mandatory_source_tier="PRIMARY_OFFICIAL",
                    min_corroborating_sources=2,
                    temporal_cutoff=cutoff_date,
                    notes=f"All sources MUST pre-date cutoff {cutoff_date or 'N/A'}. Post-cutoff sources are strictly excluded.",
                )
            )

        return ResearchPlan(
            project_id=project_id,
            topic_title=topic_title,
            content_category=content_category,
            cutoff_date=cutoff_date,
            priorities=priorities,
        )
