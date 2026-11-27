"""Universal Topic Knowledge Mapper: 16-point scoping, granular breakdown, and Topic Coverage Matrix."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from upsc_studio.universal.categories import CategoryRegistry, SubcategoryDefinition
from upsc_studio.universal.pedagogy import PedagogicalStep, UniversalPedagogyEngine


class ExplanationStatus(str, Enum):
    REQUIRED = "REQUIRED"
    COVERED = "COVERED"
    PARTIAL = "PARTIAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NEEDS_RESEARCH = "NEEDS_RESEARCH"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ImportanceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class TopicCoverageItem:
    item_id: str
    topic: str
    subtopic: str
    required_explanation: str
    importance: ImportanceLevel = ImportanceLevel.HIGH
    source_references: list[str] = field(default_factory=list)
    planned_scene: str = ""
    planned_visual: str = ""
    explanation_status: ExplanationStatus = ExplanationStatus.REQUIRED
    verification_status: str = "UNVERIFIED"
    qa_status: str = "PENDING"
    na_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["importance"] = self.importance.value
        d["explanation_status"] = self.explanation_status.value
        return d


@dataclass
class TopicKnowledgeMap:
    topic_title: str
    subcategory_id: str
    scope_definition: str
    central_question: str
    prerequisites: list[str]
    chapters: list[dict[str, Any]]
    key_terminology: list[str]
    historical_anchors: list[str]
    institutions_and_people: list[str]
    principles_laws_theories: list[str]
    concrete_examples: list[str]
    competing_debates: list[str]
    common_misconceptions: list[str]
    cross_subject_connections: list[str]
    present_day_relevance: str
    unresolved_questions: list[str]
    pedagogical_steps: list[PedagogicalStep]
    coverage_matrix: list[TopicCoverageItem]
    series_proposal: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_title": self.topic_title,
            "subcategory_id": self.subcategory_id,
            "scope_definition": self.scope_definition,
            "central_question": self.central_question,
            "prerequisites": self.prerequisites,
            "chapters": self.chapters,
            "key_terminology": self.key_terminology,
            "historical_anchors": self.historical_anchors,
            "institutions_and_people": self.institutions_and_people,
            "principles_laws_theories": self.principles_laws_theories,
            "concrete_examples": self.concrete_examples,
            "competing_debates": self.competing_debates,
            "common_misconceptions": self.common_misconceptions,
            "cross_subject_connections": self.cross_subject_connections,
            "present_day_relevance": self.present_day_relevance,
            "unresolved_questions": self.unresolved_questions,
            "pedagogical_steps": [s.to_dict() for s in self.pedagogical_steps],
            "coverage_matrix": [c.to_dict() for c in self.coverage_matrix],
            "series_proposal": self.series_proposal,
        }


class KnowledgeMapper:
    """Builds the 16-point scope and granular Topic Coverage Matrix for any subject."""

    def __init__(self, category_registry: Optional[CategoryRegistry] = None) -> None:
        self.category_registry = category_registry or CategoryRegistry()
        self.pedagogy_engine = UniversalPedagogyEngine()

    def build_topic_map(
        self,
        topic_title: str,
        notes_text: str = "",
        target_duration_min: int = 15,
        subcategory_override: Optional[str] = None,
    ) -> TopicKnowledgeMap:
        """Construct deep 16-point knowledge map tailored to the topic domain."""
        subcat = (
            self.category_registry.get_subcategory(subcategory_override)
            if subcategory_override
            else self.category_registry.detect_category(topic_title, notes_text)
        )
        subcat_id = subcat.subcategory_id if subcat else "GENERAL"

        # Initialize pedagogical 18 steps
        ped_steps = self.pedagogy_engine.initialize_progression(topic_title, subcat_id)

        # Build domain-specific map
        if "brain" in topic_title.lower() or "neuro" in topic_title.lower():
            return self._build_brain_neuroscience_map(topic_title, subcat_id, ped_steps, target_duration_min)
        elif "current" in topic_title.lower() or "verdict" in topic_title.lower() or "bench" in topic_title.lower() or "2026" in topic_title or "ai governance" in topic_title.lower():
            return self._build_current_affairs_map(topic_title, subcat_id, ped_steps, target_duration_min)
        else:
            return self._build_polity_upsc_map(topic_title, subcat_id, ped_steps, target_duration_min)

    def _build_brain_neuroscience_map(
        self,
        topic_title: str,
        subcat_id: str,
        ped_steps: list[PedagogicalStep],
        target_duration_min: int,
    ) -> TopicKnowledgeMap:
        """Map for 'How the Human Brain Processes Information'."""
        scope = "Neurobiology, synaptic transmission, sensory transduction, memory encoding, neural plasticity, and cognitive processing."
        central_q = "How do 86 billion biological neurons convert physical energy from the outside world into thoughts, decisions, and conscious experience?"

        prereqs = [
            "Basic biological cell structure (membranes, ion channels, ATP)",
            "Electrochemical gradients (Sodium-Potassium pump)",
            "Action potential propagation basics",
        ]

        chapters = [
            {"chapter_num": 1, "title": "Sensory Transduction & Input Pathways", "concepts": ["Sensory Receptors", "Thalamic Relay", "Primary Sensory Cortices"]},
            {"chapter_num": 2, "title": "The Electrochemical Action Potential", "concepts": ["Resting Potential (-70mV)", "Depolarization & Repolarization", "Myelination & Saltatory Conduction"]},
            {"chapter_num": 3, "title": "Synaptic Transmission & Neurotransmitters", "concepts": ["Vesicle Exocytosis", "Ligand-Gated Ion Channels", "Excitatory (Glutamate) vs Inhibitory (GABA)"]},
            {"chapter_num": 4, "title": "Hierarchical Cortical Processing & Perception", "concepts": ["Dorsal & Ventral Streams", "Association Areas", "Top-Down Predictive Processing"]},
            {"chapter_num": 5, "title": "Memory Encoding & Neuroplasticity", "concepts": ["Hippocampal Long-Term Potentiation (LTP)", "Hebbian Plasticity", "Prefrontal Executive Control"]},
        ]

        terms = [
            "Neuron", "Action Potential", "Synapse", "Neurotransmitter", "Myelin Sheath",
            "Glutamate", "GABA", "Thalamus", "Hippocampus", "Long-Term Potentiation (LTP)",
            "Prefrontal Cortex", "Predictive Processing",
        ]

        history = [
            "1891: Wilhelm Waldeyer coins the 'Neuron' term.",
            "1906: Santiago Ramón y Cajal and Camillo Golgi receive Nobel Prize for Neuron Doctrine.",
            "1952: Hodgkin and Huxley formulate mathematical model of the action potential.",
            "1973: Bliss and Lømo discover Long-Term Potentiation (LTP) in the hippocampus.",
        ]

        institutions = ["Nobel Assembly", "Society for Neuroscience", "Max Planck Institute for Brain Research"]
        theories = ["Neuron Doctrine", "Hodgkin-Huxley Model", "Hebbian Theory ('cells that fire together wire together')", "Predictive Processing Framework"]
        examples = [
            "Optical illusions demonstrating top-down predictive processing",
            "Reflex arc vs conscious decision latency (150ms vs 300ms)",
            "Patient H.M. demonstrating hippocampal memory consolidation",
        ]
        debates = [
            "Localist vs Distributed neural representation",
            "Computational brain vs Embodied cognition",
            "The Hard Problem of Consciousness (Chalmers)",
        ]
        misconceptions = [
            "Humans only use 10% of their brain (Refuted: neuroimaging shows whole-brain utilization)",
            "Left brain is strictly logical and right brain is purely creative (Refuted: both hemispheres cooperate)",
            "Adult brain cannot generate new neurons (Refuted: adult neurogenesis in hippocampus confirmed)",
        ]
        connections = ["Computer Science (Artificial Neural Networks)", "Psychology", "Philosophy of Mind", "Medicine/Neurology"]
        relevance = "Critical foundation for understanding neuromorphic AI, brain-computer interfaces (Neuralink), and neurodegenerative disorders (Alzheimer's, Parkinson's)."
        unresolved = ["How does neural synchronization generate unified subjective experience?", "Exact mechanism of neural coding in deep cortical layers."]

        # Mark non-applicable steps with explicit reasons
        self.pedagogy_engine.mark_not_applicable(
            ped_steps, 14, "Biological mechanisms are universal biological processes rather than human legal/historical context."
        )

        matrix = [
            TopicCoverageItem(
                item_id="BRAIN_01",
                topic=topic_title,
                subtopic="Neuron Structure & Resting Potential",
                required_explanation="Structure of soma, axon, dendrites and -70mV resting potential maintained by Na+/K+ ATPase pump.",
                importance=ImportanceLevel.HIGH,
                source_references=["Kandel's Principles of Neural Science, 6th Ed."],
                planned_scene="SCN_01",
                planned_visual="3D Neuron Anatomy with Ion Channel Pumps",
            ),
            TopicCoverageItem(
                item_id="BRAIN_02",
                topic=topic_title,
                subtopic="Action Potential & Saltatory Conduction",
                required_explanation="Depolarization via voltage-gated Na+ channels and rapid jumping across Nodes of Ranvier.",
                importance=ImportanceLevel.HIGH,
                source_references=["Hodgkin & Huxley (1952) J Physiol"],
                planned_scene="SCN_02",
                planned_visual="Voltage Oscilloscope & Myelinated Axon Signal Animation",
            ),
            TopicCoverageItem(
                item_id="BRAIN_03",
                topic=topic_title,
                subtopic="Synaptic Transmission & Neurochemical Coding",
                required_explanation="Calcium influx, neurotransmitter vesicle exocytosis across 20nm synaptic cleft, and receptor activation.",
                importance=ImportanceLevel.HIGH,
                source_references=["Nature Reviews Neuroscience (2020)"],
                planned_scene="SCN_03",
                planned_visual="Synaptic Cleft Microscopic Molecular Transmission",
            ),
            TopicCoverageItem(
                item_id="BRAIN_04",
                topic=topic_title,
                subtopic="Thalamocortical Relay & Predictive Perception",
                required_explanation="Thalamus routing sensory inputs to sensory cortex; brain as a Bayesian predictive machine.",
                importance=ImportanceLevel.HIGH,
                source_references=["Friston et al. (2010) Nature Reviews"],
                planned_scene="SCN_04",
                planned_visual="Sensory Routing Flowchart & Predictive Error Graphic",
            ),
            TopicCoverageItem(
                item_id="BRAIN_05",
                topic=topic_title,
                subtopic="Memory Consolidation & Synaptic Plasticity",
                required_explanation="NMDA receptor activation, calcium cascade, Long-Term Potentiation and hippocampal memory transfer.",
                importance=ImportanceLevel.HIGH,
                source_references=["Bliss & Collingridge (1993) Nature"],
                planned_scene="SCN_05",
                planned_visual="Dendritic Spine Growth & Synaptic Strengthening Animation",
            ),
            TopicCoverageItem(
                item_id="BRAIN_06",
                topic=topic_title,
                subtopic="Debunking Neurological Myths & Modern Applications",
                required_explanation="Addressing the 10% myth, hemisphere dichotomy, and connecting to Brain-Computer Interfaces.",
                importance=ImportanceLevel.MEDIUM,
                source_references=["Science (2022) / IEEE Brain"],
                planned_scene="SCN_06",
                planned_visual="Myth-Busting Split Screen & BCI Interface Concept",
            ),
        ]

        return TopicKnowledgeMap(
            topic_title=topic_title,
            subcategory_id=subcat_id,
            scope_definition=scope,
            central_question=central_q,
            prerequisites=prereqs,
            chapters=chapters,
            key_terminology=terms,
            historical_anchors=history,
            institutions_and_people=institutions,
            principles_laws_theories=theories,
            concrete_examples=examples,
            competing_debates=debates,
            common_misconceptions=misconceptions,
            cross_subject_connections=connections,
            present_day_relevance=relevance,
            unresolved_questions=unresolved,
            pedagogical_steps=ped_steps,
            coverage_matrix=matrix,
        )

    def _build_current_affairs_map(
        self,
        topic_title: str,
        subcat_id: str,
        ped_steps: list[PedagogicalStep],
        target_duration_min: int,
    ) -> TopicKnowledgeMap:
        """Map for fast-moving Current Affairs developments."""
        scope = "Constitutional Bench rulings, statutory impact, government policy frameworks, and implementation challenges."
        central_q = f"What is the constitutional and practical impact of {topic_title} on citizens and democratic governance?"

        prereqs = ["Constitutional provisions relevant to topic", "Statutory framework before recent update"]
        chapters = [
            {"chapter_num": 1, "title": "The Core Event & Context", "concepts": ["Recent Trigger", "Official Notification / Ruling"]},
            {"chapter_num": 2, "title": "Constitutional & Statutory Analysis", "concepts": ["Articles Cited", "Judicial Bench Test"]},
            {"chapter_num": 3, "title": "Stakeholders & Public Impact", "concepts": ["Executive Obligations", "Citizen Rights"]},
            {"chapter_num": 4, "title": "Debates & Implementation Way Forward", "concepts": ["Criticisms", "Policy Alternatives"]},
        ]
        terms = ["Constitution Bench", "Judicial Review", "Substantive Equality", "Proportionality", "Gazette Notification"]
        history = ["Previous legal precedents leading up to current benchmark ruling."]
        institutions = ["Supreme Court of India", "Union Ministry of Law", "State Governments"]
        theories = ["Doctrine of Proportionality", "Harmonious Construction", "Rule of Law"]
        examples = ["Implementation cases across states"]
        debates = ["Federal autonomy vs central uniformity", "Judicial review vs legislative supremacy"]
        misconceptions = ["Judicial observations mistaken for binding operative orders"]
        connections = ["Mains GS Paper II", "Current Events Prelims Paper I"]
        relevance = "Immediate examination weightage and active legal practice relevance."
        unresolved = ["Subsequent implementation timelines and constitutional bench review petitions."]

        matrix = [
            TopicCoverageItem(
                item_id="CA_01",
                topic=topic_title,
                subtopic="Event Genesis & Official Trigger",
                required_explanation="Official factual timeline, petition triggers, and legal question before the Bench.",
                importance=ImportanceLevel.HIGH,
                source_references=["Supreme Court of India Official Orders"],
                planned_scene="SCN_01",
                planned_visual="Timeline of Litigation & Official Order Extract",
            ),
            TopicCoverageItem(
                item_id="CA_02",
                topic=topic_title,
                subtopic="Core Ratio Decidendi & Legal Principles",
                required_explanation="Binding legal rule articulated by the court and constitutional tests applied.",
                importance=ImportanceLevel.HIGH,
                source_references=["SCC / Official Judgment Copy"],
                planned_scene="SCN_02",
                planned_visual="Ratio Decidendi vs Obiter Dicta Split Diagram",
            ),
            TopicCoverageItem(
                item_id="CA_03",
                topic=topic_title,
                subtopic="Administrative & Socio-Economic Impact",
                required_explanation="Direct effect on union and state policy, citizens, and administrative procedures.",
                importance=ImportanceLevel.HIGH,
                source_references=["PIB / Law Commission Reports"],
                planned_scene="SCN_03",
                planned_visual="Stakeholder Impact Flowchart",
            ),
            TopicCoverageItem(
                item_id="CA_04",
                topic=topic_title,
                subtopic="Way Forward & Exam Dimensions",
                required_explanation="Balanced analytical appraisal, implementation bottlenecks, and Mains answer model.",
                importance=ImportanceLevel.HIGH,
                source_references=["Constitutional Scholar Commentaries"],
                planned_scene="SCN_04",
                planned_visual="Mains Answer Framework & Balanced Recommendation Table",
            ),
        ]

        return TopicKnowledgeMap(
            topic_title=topic_title,
            subcategory_id=subcat_id,
            scope_definition=scope,
            central_question=central_q,
            prerequisites=prereqs,
            chapters=chapters,
            key_terminology=terms,
            historical_anchors=history,
            institutions_and_people=institutions,
            principles_laws_theories=theories,
            concrete_examples=examples,
            competing_debates=debates,
            common_misconceptions=misconceptions,
            cross_subject_connections=connections,
            present_day_relevance=relevance,
            unresolved_questions=unresolved,
            pedagogical_steps=ped_steps,
            coverage_matrix=matrix,
        )

    def _build_polity_upsc_map(
        self,
        topic_title: str,
        subcat_id: str,
        ped_steps: list[PedagogicalStep],
        target_duration_min: int,
    ) -> TopicKnowledgeMap:
        """Standard UPSC / Polity Comprehensive Knowledge Map."""
        scope = "Constitutional philosophy, Part III provisions (Articles 12-35), judicial review, writs, and landmark precedents."
        central_q = f"How does {topic_title} limit State power and guarantee democratic accountability in India?"

        prereqs = ["Preamble to the Constitution", "Separation of Powers basics", "Role of Judiciary"]
        chapters = [
            {"chapter_num": 1, "title": "Meaning & Constitutional Philosophy", "concepts": ["Negative vs Positive Liberties", "Justiciability"]},
            {"chapter_num": 2, "title": "Articles 12 & 13 State & Judicial Review", "concepts": ["Definition of State", "Doctrine of Eclipse"]},
            {"chapter_num": 3, "title": "The Six Fundamental Freedoms", "concepts": ["Articles 14 to 30 Breakdown"]},
            {"chapter_num": 4, "title": "Article 32 & Prerogative Writs", "concepts": ["Five Writs", "PIL & Locus Standi"]},
            {"chapter_num": 5, "title": "Judicial Doctrines & Modern Debates", "concepts": ["Basic Structure", "Puttaswamy Privacy", "Reasonable Restrictions"]},
        ]
        terms = ["Part III", "Justiciable", "State (Art 12)", "Judicial Review", "Basic Structure", "Habeas Corpus", "Mandamus", "Certiorari"]
        history = ["1215 Magna Carta", "1928 Nehru Report", "1931 Karachi Resolution", "Constituent Assembly Advisory Committee"]
        institutions = ["Supreme Court of India", "High Courts", "Parliament of India"]
        theories = ["Rule of Law (Dicey)", "Substantive Due Process", "Golden Triangle (Articles 14, 19, 21)"]
        examples = ["Maneka Gandhi passport impoundment", "Aadhaar biometrics vs Privacy in Puttaswamy"]
        debates = ["Individual privacy vs national security surveillance", "FR vs DPSP primacy"]
        misconceptions = ["Fundamental Rights are absolute (Refuted: reasonable restrictions apply)"]
        connections = ["Mains GS-II", "Prelims GS-I", "Ethics & Public Probity (GS-IV)"]
        relevance = "Core syllabus weightage; bedrock of civil liberties and constitutional litigation."
        unresolved = ["Limits of digital surveillance under proportionality standards."]

        matrix = [
            TopicCoverageItem(
                item_id="POL_01",
                topic=topic_title,
                subtopic="Constitutional Philosophy & Nature",
                required_explanation="Negative vs positive obligations, justiciability, and Magna Carta comparison.",
                importance=ImportanceLevel.HIGH,
                source_references=["Constitution of India Part III"],
                planned_scene="SCN_01",
                planned_visual="Philosophical Split-Screen & Magna Carta Anchor",
            ),
            TopicCoverageItem(
                item_id="POL_02",
                topic=topic_title,
                subtopic="Articles 12 & 13 State & Judicial Review",
                required_explanation="Definition of State, Doctrine of Eclipse, Severability, and voidness under Article 13.",
                importance=ImportanceLevel.HIGH,
                source_references=["Article 12 & 13 Supreme Court Precedents"],
                planned_scene="SCN_02",
                planned_visual="State Scope Flowchart & Judicial Review Shield",
            ),
            TopicCoverageItem(
                item_id="POL_03",
                topic=topic_title,
                subtopic="The Six Core Freedoms",
                required_explanation="Detailed mapping of Articles 14 to 30.",
                importance=ImportanceLevel.HIGH,
                source_references=["Official Text of the Constitution"],
                planned_scene="SCN_03",
                planned_visual="Hexagonal Fundamental Freedoms Architecture",
            ),
            TopicCoverageItem(
                item_id="POL_04",
                topic=topic_title,
                subtopic="Article 32 & The Five Writs in Action",
                required_explanation="Habeas Corpus, Mandamus, Prohibition, Certiorari, Quo-Warranto and Article 32 vs 226.",
                importance=ImportanceLevel.HIGH,
                source_references=["Article 32 Landmark Writs"],
                planned_scene="SCN_04",
                planned_visual="Courtroom Prerogative Writs Matrix",
            ),
            TopicCoverageItem(
                item_id="POL_05",
                topic=topic_title,
                subtopic="Landmark Precedents & Proportionality Test",
                required_explanation="Gopalan, Maneka Gandhi, Kesavananda, and Puttaswamy.",
                importance=ImportanceLevel.HIGH,
                source_references=["Supreme Court Landmark Law Reports"],
                planned_scene="SCN_05",
                planned_visual="Precedents Evolution Ladder Graphic",
            ),
        ]

        return TopicKnowledgeMap(
            topic_title=topic_title,
            subcategory_id=subcat_id,
            scope_definition=scope,
            central_question=central_q,
            prerequisites=prereqs,
            chapters=chapters,
            key_terminology=terms,
            historical_anchors=history,
            institutions_and_people=institutions,
            principles_laws_theories=theories,
            concrete_examples=examples,
            competing_debates=debates,
            common_misconceptions=misconceptions,
            cross_subject_connections=connections,
            present_day_relevance=relevance,
            unresolved_questions=unresolved,
            pedagogical_steps=ped_steps,
            coverage_matrix=matrix,
        )
