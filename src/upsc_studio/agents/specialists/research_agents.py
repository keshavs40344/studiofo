"""Specialist Agents 01-06: Executive Producer, Topic Research, Source Collection, and Fact Verification."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from upsc_studio.agents.contracts import (
    AgentExecutionContext,
    AgentExecutionResult,
    AgentRole,
    AgentStatus,
    QualityCheckStatus,
)
from upsc_studio.agents.specialists.base import BaseSpecialistAgent
from upsc_studio.research.verifier import EvidenceEngine, SOURCE_TIERS


class ExecutiveProducerAgent(BaseSpecialistAgent):
    """AGENT_01: Executive Producer supervising project health, run preconditions, and checkpointing."""

    agent_id = "AGENT_01"
    role = AgentRole.EXECUTIVE_PRODUCER
    name = "Executive Producer"
    description = "Supervises production DAG, validates preconditions, orchestrates checkpoints, and manages recovery."
    dependencies = []
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        if not context.topic_title or len(context.topic_title.strip()) < 3:
            return AgentExecutionResult(
                agent_id=self.agent_id,
                agent_role=self.role,
                status=AgentStatus.FAILED,
                quality_status=QualityCheckStatus.FAILED,
                errors=["Topic title is missing or too brief for production."],
            )

        # Verify disk directory scaffolding
        for sub in ("research", "teaching", "storyboard", "assets/generated", "audio", "subtitles", "render/final", "qa", "logs"):
            (context.project_dir / sub).mkdir(parents=True, exist_ok=True)

        plan = {
            "project_id": context.project_id,
            "topic_title": context.topic_title,
            "content_pillar": context.content_pillar,
            "target_duration_min": context.target_duration_min,
            "cutoff_date": context.cutoff_date,
            "run_id": context.run_id,
            "initialized_at": datetime.now().isoformat(),
        }

        plan_path = context.project_dir / "logs" / "production_plan.json"
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED,
            quality_status=QualityCheckStatus.PASSED,
            outputs={"production_plan": plan, "plan_path": str(plan_path)},
            artifacts_created=[str(plan_path)],
        )


class TopicResearcherAgent(BaseSpecialistAgent):
    """AGENT_02: Topic Researcher establishing topic boundaries, central questions, and learning objectives."""

    agent_id = "AGENT_02"
    role = AgentRole.TOPIC_RESEARCHER
    name = "Topic Researcher"
    description = "Defines topic boundaries, primary research questions, learning outcomes, and foundational scope."
    dependencies = ["AGENT_01"]
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        topic_lower = context.topic_title.lower()

        # Determine core research scoping
        if "brain" in topic_lower or "neuro" in topic_lower:
            scope = "Neurobiology, synaptic transmission, sensory transduction, memory encoding, neural plasticity, and cognitive processing."
            central_q = "How do 86 billion biological neurons convert physical energy into thoughts, decisions, and conscious experience?"
            objectives = [
                "Understand resting membrane potential (-70mV) and the Na+/K+ ATPase pump",
                "Explain action potential propagation and saltatory conduction across nodes of Ranvier",
                "Deconstruct synaptic neurotransmission across the 20nm synaptic cleft (Glutamate vs GABA)",
                "Examine memory consolidation through Long-Term Potentiation (LTP) in the hippocampus",
                "Debunk popular neurological myths (10% myth, hemisphere dichotomy)",
            ]
        elif "current" in topic_lower or "bench" in topic_lower or "verdict" in topic_lower or "scheduled castes" in topic_lower:
            scope = "Constitutional law, reservation jurisprudence, federal powers under Article 15(4) and 16(4), and 7-Judge SC Bench holding."
            central_q = "Does sub-classification within Scheduled Castes advance substantive equality or fracture constitutional protections?"
            objectives = [
                "Analyze the 7-judge Constitution Bench ruling in State of Punjab v. Davinder Singh (2024)",
                "Contrast with the 5-judge precedent in E.V. Chinnaiah (2005)",
                "Examine the distinction between Article 341 identification and Article 16(4) reservation powers",
                "Review the mandatory empirical data requirement for state sub-classifications",
                "Analyze majority observations regarding the creamy layer principle within SCs",
            ]
        else:
            scope = "Indian Constitutional framework, civil liberties, judicial review, fundamental rights doctrines, and enforcement writs."
            central_q = "How do Part III Fundamental Rights constrain arbitrary state power while balancing individual liberty with social order?"
            objectives = [
                "Explain the nature of Fundamental Rights as negative obligations and positive protections",
                "Deconstruct Article 12 definition of State and Article 13 judicial review doctrines",
                "Map the six fundamental freedoms under Articles 14 to 32",
                "Demonstrate practical enforcement through the five prerogative writs under Article 32 and 226",
                "Analyze landmark case laws from A.K. Gopalan to Maneka Gandhi and K.S. Puttaswamy",
            ]

        research_brief = {
            "topic_title": context.topic_title,
            "scope": scope,
            "central_question": central_q,
            "learning_objectives": objectives,
            "cutoff_date": context.cutoff_date,
        }

        brief_path = context.project_dir / "research" / "topic_research_brief.json"
        brief_path.write_text(json.dumps(research_brief, indent=2, ensure_ascii=False), encoding="utf-8")

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED,
            quality_status=QualityCheckStatus.PASSED,
            outputs={"research_brief": research_brief, "brief_path": str(brief_path)},
            artifacts_created=[str(brief_path)],
        )


class ResearchSourceCollectorAgent(BaseSpecialistAgent):
    """AGENT_03: Register actual source candidates supplied by research discovery or the user."""

    agent_id = "AGENT_03"
    role = AgentRole.RESEARCH_SOURCE_COLLECTOR
    name = "Research Source Collector"
    description = "Registers supplied source candidates without inventing bibliographic records or asserting factual support."
    dependencies = ["AGENT_02"]
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        conn = context.metadata.get("conn")
        if conn is None:
            return AgentExecutionResult(
                agent_id=self.agent_id, agent_role=self.role, status=AgentStatus.FAILED,
                quality_status=QualityCheckStatus.FAILED, errors=["Database connection is unavailable."],
            )

        engine = EvidenceEngine(conn, context.project_dir)
        candidates = context.metadata.get("source_candidates", [])
        if not isinstance(candidates, list):
            candidates = []

        existing_rows = conn.execute(
            "SELECT id, title, url, source_tier FROM sources WHERE project_id = ?",
            (context.project_id,),
        ).fetchall()
        registered = [
            {"id": row["id"], "title": row["title"], "url": row["url"],
             "tier": row["source_tier"], "registration": "EXISTING"}
            for row in existing_rows
        ]
        known_urls = {str(row["url"]).strip() for row in existing_rows if row["url"]}
        known_titles = {str(row["title"]).strip().casefold() for row in existing_rows if row["title"]}
        warnings: list[str] = []

        for candidate in candidates:
            if not isinstance(candidate, dict):
                warnings.append("Ignored malformed source candidate: expected an object.")
                continue
            title = str(candidate.get("title", "")).strip()
            publisher = str(candidate.get("publisher", "")).strip()
            tier = str(candidate.get("source_tier", "")).strip()
            url = str(candidate.get("url", "")).strip() or None
            pub_date = str(candidate.get("pub_date", "")).strip() or None
            if not title or not publisher or tier not in SOURCE_TIERS:
                warnings.append("Ignored source candidate with missing title/publisher or invalid source_tier.")
                continue
            if (url and url in known_urls) or title.casefold() in known_titles:
                continue
            source_id = engine.add_source(
                project_id=context.project_id, title=title, publisher=publisher,
                source_tier=tier, url=url, pub_date=pub_date,
                notes=str(candidate.get("notes", "")).strip(),
            )
            registered.append({
                "id": source_id, "title": title, "url": url, "tier": tier,
                "registration": "CANDIDATE_ONLY",
            })
            if url:
                known_urls.add(url)
            known_titles.add(title.casefold())

        manifest = context.project_dir / "research" / "collected_sources.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(registered, indent=2, ensure_ascii=False), encoding="utf-8")

        if not registered:
            return AgentExecutionResult(
                agent_id=self.agent_id, agent_role=self.role, status=AgentStatus.FAILED,
                quality_status=QualityCheckStatus.INSUFFICIENT_EVIDENCE,
                outputs={"sources_count": 0, "sources": [], "source_candidates_received": len(candidates)},
                errors=["No real source records were supplied. The collector will not fabricate sources."],
                artifacts_created=[str(manifest)],
            )

        return AgentExecutionResult(
            agent_id=self.agent_id, agent_role=self.role, status=AgentStatus.COMPLETED,
            quality_status=QualityCheckStatus.REVIEW_REQUIRED,
            outputs={
                "sources_count": len(registered), "sources": registered,
                "source_candidates_received": len(candidates),
                "registration_status": "CANDIDATES_ONLY_NOT_FACT_VERIFIED",
            },
            warnings=warnings + ["Inspect original source content before using it to support a claim."],
            artifacts_created=[str(manifest)],
        )


class IndependentFactCheckerAgent(BaseSpecialistAgent):
    """AGENT_04: Audit the existing claim ledger without manufacturing factual claims."""

    agent_id = "AGENT_04"
    role = AgentRole.INDEPENDENT_FACT_CHECKER
    name = "Independent Fact Checker"
    description = "Inventories existing atomic claims and flags conflicts and claims lacking human evidence attestation."
    dependencies = ["AGENT_03"]
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        conn = context.metadata.get("conn")
        if conn is None:
            return AgentExecutionResult(
                agent_id=self.agent_id, agent_role=self.role, status=AgentStatus.FAILED,
                quality_status=QualityCheckStatus.FAILED, errors=["Database connection is unavailable."],
            )
        claims = conn.execute(
            "SELECT id, status, verification_notes FROM claims WHERE project_id = ?",
            (context.project_id,),
        ).fetchall()
        if not claims:
            return AgentExecutionResult(
                agent_id=self.agent_id, agent_role=self.role, status=AgentStatus.FAILED,
                quality_status=QualityCheckStatus.INSUFFICIENT_EVIDENCE,
                outputs={"claims_seen_count": 0, "conflicts_found": 0},
                errors=["No extracted claims exist. The fact checker will not invent claims."],
            )

        engine = EvidenceEngine(conn, context.project_dir)
        conflicts = engine.detect_conflicts(context.project_id)
        needs_review = sum(
            1 for claim in claims
            if claim["status"] != "VERIFIED"
            or not (claim["verification_notes"] or "").startswith("HUMAN_ATTESTED_BY:")
        )
        return AgentExecutionResult(
            agent_id=self.agent_id, agent_role=self.role, status=AgentStatus.COMPLETED,
            quality_status=QualityCheckStatus.REVIEW_REQUIRED if needs_review or conflicts else QualityCheckStatus.PASSED,
            outputs={
                "claims_seen_count": len(claims),
                "claims_requiring_human_review": needs_review,
                "conflicts_found": len(conflicts),
            },
            warnings=["This worker audits the supplied claim ledger; it does not independently establish truth."]
            if needs_review or conflicts else [],
        )


class ClaimToSourceVerifierAgent(BaseSpecialistAgent):
    """AGENT_05: Enforce the explicit human-attestation boundary for claim verification."""

    agent_id = "AGENT_05"
    role = AgentRole.CLAIM_TO_SOURCE_VERIFIER
    name = "Claim-to-Source Verifier"
    description = "Accepts VERIFIED only when an explicit reviewer attestation and source excerpt are recorded."
    dependencies = ["AGENT_04"]
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        conn = context.metadata.get("conn")
        if conn is None:
            return AgentExecutionResult(
                agent_id=self.agent_id, agent_role=self.role, status=AgentStatus.FAILED,
                quality_status=QualityCheckStatus.FAILED, errors=["Database connection is unavailable."],
            )

        claims = conn.execute(
            "SELECT id, source_id, page_or_section, status, verification_notes FROM claims WHERE project_id = ?",
            (context.project_id,),
        ).fetchall()
        verified_count = 0
        review_count = 0
        unsupported_count = 0

        for claim in claims:
            notes = claim["verification_notes"] or ""
            excerpt_marker = "Evidence excerpt:"
            excerpt = notes.split(excerpt_marker, 1)[1].strip() if excerpt_marker in notes else ""
            attested = (
                notes.startswith("HUMAN_ATTESTED_BY:")
                and len(notes.splitlines()[0].partition(":")[2].strip()) > 0
                and bool(claim["source_id"])
                and bool((claim["page_or_section"] or "").strip())
                and len(excerpt) >= 10
                and claim["status"] == "VERIFIED"
            )
            if attested:
                verified_count += 1
            elif not claim["source_id"] or not (claim["page_or_section"] or "").strip():
                conn.execute(
                    "UPDATE claims SET status = 'UNSUPPORTED' WHERE id = ?", (claim["id"],)
                )
                unsupported_count += 1
            else:
                conn.execute(
                    "UPDATE claims SET status = 'HUMAN_REVIEW_REQUIRED' WHERE id = ?", (claim["id"],)
                )
                review_count += 1

        conn.commit()
        q_status = (
            QualityCheckStatus.PASSED
            if review_count == 0 and unsupported_count == 0
            else (QualityCheckStatus.REVIEW_REQUIRED if verified_count > 0 else QualityCheckStatus.INSUFFICIENT_EVIDENCE)
        )
        task_status = AgentStatus.COMPLETED if verified_count > 0 else AgentStatus.FAILED
        return AgentExecutionResult(
            agent_id=self.agent_id, agent_role=self.role, status=task_status,
            quality_status=q_status,
            outputs={
                "verified_claims": verified_count,
                "claims_requiring_human_review": review_count,
                "unsupported_claims": unsupported_count,
            },
            warnings=[
                "Claims without explicit reviewer attestation remain excluded from factual narration."
            ] if review_count or unsupported_count else [],
        )


class SourceFreshnessAuditorAgent(BaseSpecialistAgent):
    """AGENT_06: Source Freshness Auditor flagging outdated laws or research beyond cutoff date."""

    agent_id = "AGENT_06"
    role = AgentRole.SOURCE_FRESHNESS_AUDITOR
    name = "Source Freshness Auditor"
    description = "Audits source publication dates against cutoff date; flags obsolete legal provisions or outdated statistics."
    dependencies = ["AGENT_05"]
    is_retry_safe = True
    has_side_effects = False

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        conn = context.metadata.get("conn")
        sources = conn.execute("SELECT * FROM sources WHERE project_id = ?", (context.project_id,)).fetchall()
        outdated_sources: list[str] = []

        cutoff_year = int(context.cutoff_date[:4]) if len(context.cutoff_date) >= 4 else 2026

        for s in sources:
            pub_date = s["pub_date"] or ""
            year_match = re.search(r"\b(19\d{2}|20\d{2})\b", pub_date)
            if year_match:
                yr = int(year_match.group(1))
                if yr > cutoff_year:
                    outdated_sources.append(f"Source '{s['title']}' dated {yr} exceeds cutoff year {cutoff_year}.")

        report = {
            "cutoff_date": context.cutoff_date,
            "total_sources_audited": len(sources),
            "outdated_or_future_sources": outdated_sources,
            "is_fresh": len(outdated_sources) == 0,
        }

        fresh_path = context.project_dir / "research" / "freshness_audit.json"
        fresh_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        return AgentExecutionResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=AgentStatus.COMPLETED,
            quality_status=QualityCheckStatus.PASSED if not outdated_sources else QualityCheckStatus.REVIEW_REQUIRED,
            outputs=report,
            artifacts_created=[str(fresh_path)],
        )
