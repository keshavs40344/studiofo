"""Structured Topic Map: Hierarchical concept breakdown, learning objectives, prerequisites, and misconceptions."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class ConceptCategory(str, Enum):
    DEFINITION = "DEFINITION"
    CORE_PRINCIPLE = "CORE_PRINCIPLE"
    MECHANISM = "MECHANISM"
    HISTORICAL_DEVELOPMENT = "HISTORICAL_DEVELOPMENT"
    CAUSES_CONSEQUENCES = "CAUSES_CONSEQUENCES"
    EXAMPLE_CASE_STUDY = "EXAMPLE_CASE_STUDY"
    LIMITATION_COUNTEREXAMPLE = "LIMITATION_COUNTEREXAMPLE"
    MISCONCEPTION = "MISCONCEPTION"
    EXAM_CONNECTION = "EXAM_CONNECTION"


class ContentPillar(str, Enum):
    UPSC = "upsc"
    GENERAL_KNOWLEDGE = "general_knowledge"
    CURRENT_AFFAIRS = "current_affairs"
    DEEP_DIVE = "deep_dive"


@dataclass
class TopicConcept:
    concept_id: str
    name: str
    category: ConceptCategory
    definition: str
    prerequisites: list[str] = field(default_factory=list)
    mechanisms: list[str] = field(default_factory=list)
    historical_context: Optional[str] = None
    causes_and_consequences: list[dict[str, str]] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    counterexamples_and_limitations: list[str] = field(default_factory=list)
    common_misconceptions: list[dict[str, str]] = field(default_factory=list)
    exam_connections: dict[str, Any] = field(default_factory=dict)
    verified_claim_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        return d


@dataclass
class StructuredTopicMap:
    topic_id: str
    title: str
    content_pillar: ContentPillar
    learning_objectives: list[str] = field(default_factory=list)
    prerequisite_knowledge: list[str] = field(default_factory=list)
    required_concepts: list[TopicConcept] = field(default_factory=list)
    mind_map: dict[str, Any] = field(default_factory=dict)
    coverage_matrix: dict[str, bool] = field(default_factory=dict)
    research_cutoff_date: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "title": self.title,
            "content_pillar": self.content_pillar.value,
            "learning_objectives": self.learning_objectives,
            "prerequisite_knowledge": self.prerequisite_knowledge,
            "required_concepts": [c.to_dict() for c in self.required_concepts],
            "mind_map": self.mind_map,
            "coverage_matrix": self.coverage_matrix,
            "research_cutoff_date": self.research_cutoff_date,
        }


class TopicMapBuilder:
    """Builds an exhaustive, pedagogically sound topic map from title, category, and verified claims."""

    def build_topic_map(
        self,
        topic_title: str,
        content_category: str = "upsc",
        verified_claims: list[dict[str, Any]] | None = None,
        cutoff_date: str | None = None,
    ) -> StructuredTopicMap:
        category_enum = ContentPillar(content_category.lower())
        claims = verified_claims or []
        t_lower = topic_title.lower()

        # Enforce cutoff date requirement for Current Affairs
        if category_enum == ContentPillar.CURRENT_AFFAIRS and not cutoff_date:
            raise ValueError("Current Affairs projects require an explicit cutoff_date to prevent anachronisms.")

        # 1. Learning Objectives (Action-oriented, Bloom's Taxonomy)
        objectives = self._derive_learning_objectives(topic_title, category_enum)

        # 2. Prerequisite Knowledge
        prerequisites = self._derive_prerequisites(topic_title, category_enum)

        # 3. Required Concepts
        concepts = self._derive_concepts(topic_title, category_enum, claims)

        # 4. Mind Map Nodes & Edges
        mind_map = self._build_mind_map(topic_title, concepts)

        # 5. Coverage Matrix
        cov_matrix = {c.concept_id: len(c.verified_claim_ids) > 0 for c in concepts}

        return StructuredTopicMap(
            topic_id=f"top_{abs(hash(topic_title)) % 1000000:06d}",
            title=topic_title,
            content_pillar=category_enum,
            learning_objectives=objectives,
            prerequisite_knowledge=prerequisites,
            required_concepts=concepts,
            mind_map=mind_map,
            coverage_matrix=cov_matrix,
            research_cutoff_date=cutoff_date,
        )

    def _derive_learning_objectives(self, title: str, pillar: ContentPillar) -> list[str]:
        base_verbs = ["Explain", "Analyze", "Evaluate", "Examine", "Distinguish"]
        if pillar == ContentPillar.UPSC:
            return [
                f"Define {title} and trace its constitutional and institutional foundations.",
                f"Analyze the core operational mechanisms and statutory procedures governing {title}.",
                f"Evaluate landmark judicial interpretations and landmark rulings concerning {title}.",
                f"Examine systemic challenges, implementation bottlenecks, and proposed institutional reforms.",
                f"Synthesize comprehensive Prelims factual dimensions and Mains analytical answer frameworks for {title}.",
            ]
        elif pillar == ContentPillar.GENERAL_KNOWLEDGE:
            return [
                f"Define {title} and understand its foundational scientific or historical principles.",
                f"Trace how {title} functions step-by-step in the real world.",
                f"Identify real-world examples, applications, and technological implementations of {title}.",
                f"Clarify common public misconceptions and boundary limitations regarding {title}.",
            ]
        elif pillar == ContentPillar.CURRENT_AFFAIRS:
            return [
                f"Identify the background catalyst and recent developments surrounding {title}.",
                f"Map the key stakeholders, institutional reactions, and immediate policy outcomes.",
                f"Analyze conflicting perspectives, critical arguments, and socio-economic ramifications.",
                f"Trace future implications and unresolved questions within the recorded timeframe.",
            ]
        else:  # DEEP_DIVE
            return [
                f"Deconstruct the fundamental systemic architecture of {title}.",
                f"Investigate underlying historical evolutions and structural turning points.",
                f"Examine competing analytical paradigms, academic debates, and empirical data.",
                f"Evaluate multi-dimensional consequences and long-term societal trajectories.",
            ]

    def _derive_prerequisites(self, title: str, pillar: ContentPillar) -> list[str]:
        t_lower = title.lower()
        if "right" in t_lower or "constitution" in t_lower or "polity" in t_lower:
            return [
                "Basic understanding of Constitutional Preamble and Rule of Law",
                "Separation of Powers between Executive, Legislature, and Judiciary",
                "Distinction between Justiciable Guarantees and Non-justiciable Directive Principles",
            ]
        elif "heat" in t_lower or "climate" in t_lower or "urban" in t_lower:
            return [
                "Basic concepts of solar radiation, albedo, and thermal absorption",
                "Understanding of urban surface geometry and anthropogenic heat emissions",
            ]
        elif "economy" in t_lower or "monetary" in t_lower or "bank" in t_lower:
            return [
                "Concept of money supply, inflation, and interest rate channels",
                "Role of Central Bank as statutory regulatory authority",
            ]
        return [
            f"Introductory familiarity with core terminology of {title}",
            "Basic understanding of cause-and-effect relationship in institutional systems",
        ]

    def _derive_concepts(
        self,
        title: str,
        pillar: ContentPillar,
        claims: list[dict[str, Any]],
    ) -> list[TopicConcept]:
        t_lower = title.lower()
        claim_map = {str(c.get("id")): c.get("statement", "") for c in claims}
        all_claim_ids = list(claim_map.keys())

        concepts: list[TopicConcept] = []

        # 1. Definition & Scope
        c1_claims = [cid for cid, s in claim_map.items() if any(k in s.lower() for k in ("article", "definition", "provides", "guarantees", "part iii", "concept", "means"))] or all_claim_ids[:1]
        concepts.append(
            TopicConcept(
                concept_id="CPT_01_DEF",
                name="Foundational Definition & Scope",
                category=ConceptCategory.DEFINITION,
                definition=f"The authoritative definition, scope, and constitutional/institutional mandate of {title}.",
                prerequisites=["Basic institutional vocabulary"],
                mechanisms=[f"Statutory and constitutional enactment establishing {title}."],
                historical_context="Originating through statutory codification and foundational charter adoption.",
                causes_and_consequences=[
                    {"cause": "Need for institutional guarantee", "consequence": "Creation of enforceable rights and legal parameters"}
                ],
                examples=[f"Primary legal/factual baseline as codified in official documentation."],
                counterexamples_and_limitations=["Subject to reasonable restrictions and statutory boundaries."],
                common_misconceptions=[
                    {
                        "misconception": "Rights/principles are absolute without public interest limits.",
                        "correction": "All constitutional and legal mechanisms operate within proportional, legally defined limits.",
                    }
                ],
                exam_connections={"relevance": "Definition and constitutional article mapping", "paper": "GS Paper II" if pillar == ContentPillar.UPSC else "General Paper"},
                verified_claim_ids=c1_claims,
            )
        )

        # 2. Functional Mechanism & Process Sequence
        c2_claims = [cid for cid, s in claim_map.items() if any(k in s.lower() for k in ("process", "procedure", "how", "enforcement", "writs", "court", "mechanism"))] or all_claim_ids[1:2]
        concepts.append(
            TopicConcept(
                concept_id="CPT_02_MECH",
                name="Functional Mechanism & Operative Sequence",
                category=ConceptCategory.MECHANISM,
                definition=f"The procedural and operational mechanism through which {title} executes and produces real-world outcomes.",
                prerequisites=["Understanding of administrative/legal process"],
                mechanisms=[
                    "Initiation / Trigger phase (e.g., petition, biological trigger, or policy catalyst).",
                    "Institutional or physical processing sequence under established rules.",
                    "Outcome delivery and judicial/statutory enforcement.",
                ],
                causes_and_consequences=[
                    {"cause": "Procedural compliance", "consequence": "Predictable, transparent institutional output"}
                ],
                examples=["Prerogative writs enforcement mechanism under Article 32 / regulatory procedures."],
                counterexamples_and_limitations=["Procedural delays and administrative friction."],
                common_misconceptions=[
                    {
                        "misconception": "Outcomes occur instantaneously upon statutory notice.",
                        "correction": "Due process requires multi-stage verification and hearing before binding decisions.",
                    }
                ],
                exam_connections={"relevance": "Procedural safeguards and institutional mandates", "paper": "GS Paper II" if pillar == ContentPillar.UPSC else "General Paper"},
                verified_claim_ids=c2_claims,
            )
        )

        # 3. Evolution & Landmark Precedents / Empirical Catalysts
        c3_claims = [cid for cid, s in claim_map.items() if any(k in s.lower() for k in ("case", "judgment", "history", "evolution", "supreme court", "maneka", "1978"))] or all_claim_ids[2:3]
        concepts.append(
            TopicConcept(
                concept_id="CPT_03_EVOL",
                name="Historical Evolution & Precedents",
                category=ConceptCategory.HISTORICAL_DEVELOPMENT,
                definition=f"The chronological milestones, judicial rulings, or empirical shifts that shaped {title}.",
                historical_context="Shift from formalistic/literal interpretation to substantive modern doctrine.",
                mechanisms=["Judicial review and doctrine expansion through constitutional bench decisions."],
                causes_and_consequences=[
                    {"cause": "Evolving societal needs", "consequence": "Doctrinal widening of scope and procedural fairness"}
                ],
                examples=["Maneka Gandhi v. Union of India (1978) establishing just, fair, and reasonable procedure."],
                counterexamples_and_limitations=["Risk of judicial overreach vs executive policymaking mandate."],
                common_misconceptions=[
                    {
                        "misconception": "Judicial bench observations in hearings are binding law.",
                        "correction": "Only the ratio decidendi in the final written judgment constitutes binding precedent.",
                    }
                ],
                exam_connections={"relevance": "Case law evolution and doctrine of due process", "paper": "GS Paper II" if pillar == ContentPillar.UPSC else "General Paper"},
                verified_claim_ids=c3_claims,
            )
        )

        # 4. Critical Limitations, Counterexamples & Contemporary Debates
        c4_claims = [cid for cid, s in claim_map.items() if cid not in (c1_claims + c2_claims + c3_claims)] or all_claim_ids[3:]
        concepts.append(
            TopicConcept(
                concept_id="CPT_04_LIMITS",
                name="Systemic Bottlenecks & Reform Dimensions",
                category=ConceptCategory.LIMITATION_COUNTEREXAMPLE,
                definition=f"The structural constraints, counterarguments, and contemporary reform debates regarding {title}.",
                mechanisms=["Audit oversight, legislative amendments, and administrative feedback loops."],
                causes_and_consequences=[
                    {"cause": "Institutional capacity constraints", "consequence": "Pendency, under-utilization, and calls for modernization"}
                ],
                examples=["Pendency of writ petitions and need for specialized administrative tribunals."],
                counterexamples_and_limitations=["Resource constraints, jurisdictional overlaps, and federal frictions."],
                common_misconceptions=[
                    {
                        "misconception": "Legislative amendment alone resolves systemic structural inefficiencies.",
                        "correction": "Systemic efficacy requires ground-level administrative capacity and digital infrastructure.",
                    }
                ],
                exam_connections={"relevance": "Way forward, institutional reforms, and answer conclusions", "paper": "GS Paper II" if pillar == ContentPillar.UPSC else "General Paper"},
                verified_claim_ids=c4_claims,
            )
        )

        return concepts

    def _build_mind_map(self, title: str, concepts: list[TopicConcept]) -> dict[str, Any]:
        nodes = [{"id": "ROOT", "label": title, "type": "root"}]
        edges = []

        for c in concepts:
            nodes.append({"id": c.concept_id, "label": c.name, "type": "concept"})
            edges.append({"from": "ROOT", "to": c.concept_id})

            # Sub-branches
            def_id = f"{c.concept_id}_def"
            nodes.append({"id": def_id, "label": "Definition & Scope", "type": "attribute"})
            edges.append({"from": c.concept_id, "to": def_id})

            mech_id = f"{c.concept_id}_mech"
            nodes.append({"id": mech_id, "label": "Mechanism", "type": "attribute"})
            edges.append({"from": c.concept_id, "to": mech_id})

            ex_id = f"{c.concept_id}_ex"
            nodes.append({"id": ex_id, "label": "Examples & Precedents", "type": "attribute"})
            edges.append({"from": c.concept_id, "to": ex_id})

            lim_id = f"{c.concept_id}_lim"
            nodes.append({"id": lim_id, "label": "Debates & Limits", "type": "attribute"})
            edges.append({"from": c.concept_id, "to": lim_id})

        return {"nodes": nodes, "edges": edges}
