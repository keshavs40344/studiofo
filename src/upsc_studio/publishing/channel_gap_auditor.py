"""Channel Content Gap Auditor: Maps YouTube channel videos to UPSC Knowledge Graph and builds upgrade plans."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from upsc_studio.syllabus.knowledge_catalogue import CatalogueStatus, KnowledgeCatalogue
from upsc_studio.syllabus.knowledge_graph import KnowledgeGraph, KnowledgeNode


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GapStatus(str, Enum):
    NO_VIDEO = "NO_VIDEO"
    INCOMPLETE_COVERAGE = "INCOMPLETE_COVERAGE"
    OUTDATED_FACTS = "OUTDATED_FACTS"
    NEEDS_BETTER_EXPLANATION = "NEEDS_BETTER_EXPLANATION"
    MEETS_QUALITY_STANDARD = "MEETS_QUALITY_STANDARD"


@dataclass
class ChannelVideoItem:
    video_id: str
    title: str
    description: str = ""
    published_date: str = ""
    url: str = ""
    transcript: str = ""
    view_count: int = 0
    duration_sec: int = 0


@dataclass
class TopicAuditResult:
    node_id: str
    paper: str
    subject: str
    major_topic: str
    microtopic: str
    gap_status: GapStatus
    matched_video_id: Optional[str] = None
    matched_video_title: Optional[str] = None
    matched_video_url: Optional[str] = None
    confidence_score: float = 0.0
    detected_gaps: list[str] = field(default_factory=list)
    upgrade_recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["gap_status"] = self.gap_status.value
        return d


@dataclass
class ChannelAuditReport:
    channel_url: str
    audited_at: str
    total_videos_scanned: int
    total_syllabus_topics: int
    fully_covered_count: int
    incomplete_count: int
    outdated_count: int
    needs_better_explanation_count: int
    no_video_count: int
    topic_results: list[TopicAuditResult]
    upgrade_plan: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_url": self.channel_url,
            "audited_at": self.audited_at,
            "total_videos_scanned": self.total_videos_scanned,
            "total_syllabus_topics": self.total_syllabus_topics,
            "fully_covered_count": self.fully_covered_count,
            "incomplete_count": self.incomplete_count,
            "outdated_count": self.outdated_count,
            "needs_better_explanation_count": self.needs_better_explanation_count,
            "no_video_count": self.no_video_count,
            "topic_results": [r.to_dict() for r in self.topic_results],
            "upgrade_plan": self.upgrade_plan,
        }


class ChannelGapAuditor:
    """Evaluates channel video inventory against the syllabus knowledge graph without fabricating evidence."""

    def __init__(self, graph: KnowledgeGraph, catalogue: Optional[KnowledgeCatalogue] = None) -> None:
        self.graph = graph
        self.catalogue = catalogue

    def audit_channel_videos(
        self,
        channel_url: str,
        videos: list[ChannelVideoItem],
        reference_year: int = 2026,
    ) -> ChannelAuditReport:
        """Analyze accessible videos against knowledge graph and generate an upgrade plan."""
        topic_results: list[TopicAuditResult] = []
        upgrade_plan: list[dict[str, Any]] = []

        now = utc_now_iso()
        all_nodes = list(self.graph.nodes.values())

        for node in all_nodes:
            best_match, score = self._find_best_matching_video(node, videos)

            if not best_match or score < 0.25:
                # No video found for this topic
                res = TopicAuditResult(
                    node_id=node.node_id,
                    paper=node.paper,
                    subject=node.subject,
                    major_topic=node.major_topic,
                    microtopic=node.microtopic,
                    gap_status=GapStatus.NO_VIDEO,
                    confidence_score=score,
                    detected_gaps=["No matching video found in accessible channel inventory."],
                    upgrade_recommendation=f"Produce new dedicated Hinglish documentary covering '{node.microtopic}' ({node.required_depth.value}).",
                )
                topic_results.append(res)
                upgrade_plan.append({
                    "priority": "HIGH" if "POL_FR" in node.node_id else "MEDIUM",
                    "action": "CREATE_NEW_VIDEO",
                    "node_id": node.node_id,
                    "target_topic": f"{node.major_topic}: {node.microtopic}",
                    "reason": "Topic absent from channel.",
                })
                continue

            # Analyze the matched video
            gap_status, detected_gaps, upgrade_rec = self._assess_video_coverage(
                node=node,
                video=best_match,
                score=score,
                reference_year=reference_year,
            )

            res = TopicAuditResult(
                node_id=node.node_id,
                paper=node.paper,
                subject=node.subject,
                major_topic=node.major_topic,
                microtopic=node.microtopic,
                gap_status=gap_status,
                matched_video_id=best_match.video_id,
                matched_video_title=best_match.title,
                matched_video_url=best_match.url or f"https://www.youtube.com/watch?v={best_match.video_id}",
                confidence_score=round(score, 3),
                detected_gaps=detected_gaps,
                upgrade_recommendation=upgrade_rec,
            )
            topic_results.append(res)

            # Update catalogue if catalogue instance exists
            if self.catalogue:
                if gap_status == GapStatus.MEETS_QUALITY_STANDARD:
                    try:
                        self.catalogue.update_status(
                            node_id=node.node_id,
                            new_status=CatalogueStatus.PUBLISHED,
                            published_video_url=res.matched_video_url,
                            notes=f"Audited match: {best_match.title}",
                        )
                    except Exception:
                        pass
                elif gap_status in {GapStatus.OUTDATED_FACTS, GapStatus.INCOMPLETE_COVERAGE}:
                    try:
                        self.catalogue.update_status(
                            node_id=node.node_id,
                            new_status=CatalogueStatus.NEEDS_REVISION,
                            published_video_url=res.matched_video_url,
                            notes=f"Audit flagged: {'; '.join(detected_gaps)}",
                        )
                    except Exception:
                        pass

            if gap_status != GapStatus.MEETS_QUALITY_STANDARD:
                upgrade_plan.append({
                    "priority": "HIGH" if gap_status in {GapStatus.OUTDATED_FACTS, GapStatus.INCOMPLETE_COVERAGE} else "MEDIUM",
                    "action": "UPGRADE_EXISTING_VIDEO",
                    "node_id": node.node_id,
                    "target_topic": f"{node.major_topic}: {node.microtopic}",
                    "existing_video": {
                        "id": best_match.video_id,
                        "title": best_match.title,
                        "url": res.matched_video_url,
                    },
                    "reason": "; ".join(detected_gaps),
                    "recommendation": upgrade_rec,
                })

        # Count distribution
        counts = {s: 0 for s in GapStatus}
        for r in topic_results:
            counts[r.gap_status] += 1

        return ChannelAuditReport(
            channel_url=channel_url,
            audited_at=now,
            total_videos_scanned=len(videos),
            total_syllabus_topics=len(all_nodes),
            fully_covered_count=counts[GapStatus.MEETS_QUALITY_STANDARD],
            incomplete_count=counts[GapStatus.INCOMPLETE_COVERAGE],
            outdated_count=counts[GapStatus.OUTDATED_FACTS],
            needs_better_explanation_count=counts[GapStatus.NEEDS_BETTER_EXPLANATION],
            no_video_count=counts[GapStatus.NO_VIDEO],
            topic_results=topic_results,
            upgrade_plan=upgrade_plan,
        )

    def _find_best_matching_video(
        self,
        node: KnowledgeNode,
        videos: list[ChannelVideoItem],
    ) -> tuple[Optional[ChannelVideoItem], float]:
        """Match video by keywords, title tokens, and microtopic semantics."""
        best_item: Optional[ChannelVideoItem] = None
        best_score = 0.0

        keywords_lower = [k.lower() for k in node.keywords]
        micro_tokens = set(re.findall(r"\w+", node.microtopic.lower()))
        major_lower = node.major_topic.lower()

        for vid in videos:
            t_lower = vid.title.lower()
            d_lower = vid.description.lower()
            tr_lower = vid.transcript.lower()
            combined = f"{t_lower} {d_lower} {tr_lower}"

            # Title matches score heavily
            score = 0.0
            if major_lower in t_lower:
                score += 0.35
            for kw in keywords_lower:
                if kw in t_lower:
                    score += 0.25
                elif kw in combined:
                    score += 0.08

            token_hits = sum(1 for tok in micro_tokens if tok in combined)
            if micro_tokens:
                score += 0.3 * (token_hits / len(micro_tokens))

            score = min(1.0, score)
            if score > best_score:
                best_score = score
                best_item = vid

        return best_item, best_score

    def _assess_video_coverage(
        self,
        node: KnowledgeNode,
        video: ChannelVideoItem,
        score: float,
        reference_year: int = 2026,
    ) -> tuple[GapStatus, list[str], str]:
        gaps: list[str] = []

        # 1. Check for outdated date references
        if video.published_date:
            try:
                pub_year = int(video.published_date[:4])
                if reference_year - pub_year >= 4:
                    gaps.append(f"Video published in {pub_year} (>= 4 years old); legal provisions, judgments or data require updating.")
            except Exception:
                pass

        # 2. Check duration sufficiency
        if video.duration_sec and video.duration_sec < 180:
            gaps.append("Short video (< 3 mins); insufficient duration for UPSC analytical depth.")

        # 3. Check transcript coverage of key concepts
        if video.transcript:
            tr_lower = video.transcript.lower()
            missing_kws = [kw for kw in node.keywords if kw.lower() not in tr_lower]
            if len(missing_kws) > len(node.keywords) * 0.5:
                gaps.append(f"Transcript lacks explanation for core concepts: {', '.join(missing_kws[:3])}.")
        else:
            if score < 0.6:
                gaps.append("Title partially matched, but full topic depth cannot be confirmed without transcript.")

        # Classify status
        if any("outdated" in g.lower() or "year" in g.lower() for g in gaps):
            status = GapStatus.OUTDATED_FACTS
            rec = "Update video with latest constitutional case law, statutory amendments, and recent statistics."
        elif any("insufficient duration" in g.lower() or "lacks explanation" in g.lower() for g in gaps):
            status = GapStatus.INCOMPLETE_COVERAGE
            rec = "Expand explanation into a comprehensive documentary lesson covering missing dimensions."
        elif score < 0.55 or gaps:
            status = GapStatus.NEEDS_BETTER_EXPLANATION
            rec = "Improve teaching pedagogy: add step-by-step mechanism, visual diagrams, and UPSC PYQs."
        else:
            status = GapStatus.MEETS_QUALITY_STANDARD
            rec = "Content meets syllabus requirements. Retain and link to topic playlist."

        return status, gaps, rec
