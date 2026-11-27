"""UPSC Syllabus Knowledge Graph: Authoritative multi-tier breakdown and prerequisite engine."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class UPSCStage(str, Enum):
    PRELIMS = "PRELIMS"
    MAINS = "MAINS"
    ESSAY = "ESSAY"
    OPTIONAL = "OPTIONAL"
    INTERVIEW = "INTERVIEW"
    CURRENT_AFFAIRS = "CURRENT_AFFAIRS"


class TopicDepth(str, Enum):
    FOUNDATION = "FOUNDATION"
    CONCEPT = "CONCEPT"
    ANALYTICAL = "ANALYTICAL"
    APPLICATION_PYQ = "APPLICATION_PYQ"


@dataclass
class KnowledgeNode:
    """Microtopic node in the UPSC syllabus knowledge graph."""
    node_id: str
    stage: UPSCStage
    paper: str
    subject: str
    major_topic: str
    subtopic: str
    microtopic: str
    prerequisites: list[str] = field(default_factory=list)
    connected_entries: list[str] = field(default_factory=list)
    relevant_pyqs: list[str] = field(default_factory=list)
    required_depth: TopicDepth = TopicDepth.CONCEPT
    keywords: list[str] = field(default_factory=list)
    estimated_duration_min: int = 15

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["stage"] = self.stage.value
        d["required_depth"] = self.required_depth.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeNode:
        payload = dict(data)
        payload["stage"] = UPSCStage(payload["stage"])
        payload["required_depth"] = TopicDepth(payload["required_depth"])
        return cls(**payload)


class KnowledgeGraph:
    """Official UPSC Syllabus Knowledge Graph with prerequisite DAG and topic playlists."""

    def __init__(self) -> None:
        self.nodes: dict[str, KnowledgeNode] = {}
        self._init_default_graph()

    def add_node(self, node: KnowledgeNode) -> None:
        self.nodes[node.node_id] = node

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        return self.nodes.get(node_id)

    def list_nodes(
        self,
        paper: Optional[str] = None,
        subject: Optional[str] = None,
        stage: Optional[UPSCStage] = None,
        major_topic: Optional[str] = None,
    ) -> list[KnowledgeNode]:
        results = list(self.nodes.values())
        if stage:
            results = [n for n in results if n.stage == stage]
        if paper:
            results = [n for n in results if n.paper.lower() == paper.lower()]
        if subject:
            results = [n for n in results if n.subject.lower() == subject.lower()]
        if major_topic:
            results = [n for n in results if n.major_topic.lower() == major_topic.lower()]
        return results

    def get_prerequisites(self, node_id: str) -> list[KnowledgeNode]:
        node = self.get_node(node_id)
        if not node:
            return []
        return [self.nodes[pid] for pid in node.prerequisites if pid in self.nodes]

    def get_learning_path(self, node_id: str) -> list[KnowledgeNode]:
        """Return topological order of prerequisite nodes leading up to target node."""
        visited: set[str] = set()
        path: list[KnowledgeNode] = []

        def dfs(current_id: str) -> None:
            if current_id in visited:
                return
            visited.add(current_id)
            c_node = self.nodes.get(current_id)
            if not c_node:
                return
            for pid in c_node.prerequisites:
                if pid in self.nodes:
                    dfs(pid)
            path.append(c_node)

        dfs(node_id)
        return path

    def get_topic_playlist(self, major_topic: str) -> list[KnowledgeNode]:
        """Return ordered playlist of lessons for a major topic based on dependencies."""
        topic_nodes = [n for n in self.nodes.values() if n.major_topic.lower() == major_topic.lower()]
        id_set = {n.node_id for n in topic_nodes}

        # Topological sorting within the topic subset
        visited: set[str] = set()
        ordered: list[KnowledgeNode] = []

        def dfs(node: KnowledgeNode) -> None:
            if node.node_id in visited:
                return
            visited.add(node.node_id)
            for pid in node.prerequisites:
                if pid in id_set and pid in self.nodes:
                    dfs(self.nodes[pid])
            ordered.append(node)

        for n in topic_nodes:
            dfs(n)
        return ordered

    def get_coverage_breakdown(self) -> dict[str, Any]:
        """Return syllabus nodes distribution across stages, papers, and subjects."""
        by_stage: dict[str, int] = {}
        by_paper: dict[str, int] = {}
        by_subject: dict[str, int] = {}

        for n in self.nodes.values():
            s_val = n.stage.value
            by_stage[s_val] = by_stage.get(s_val, 0) + 1

            p_val = n.paper
            by_paper[p_val] = by_paper.get(p_val, 0) + 1

            sub_val = n.subject
            by_subject[sub_val] = by_subject.get(sub_val, 0) + 1

        return {
            "total_nodes": len(self.nodes),
            "by_stage": by_stage,
            "by_paper": by_paper,
            "by_subject": by_subject,
        }

    def _init_default_graph(self) -> None:
        """Seed official UPSC syllabus across all papers, with deep breakdown for Fundamental Rights."""
        # -------------------------------------------------------------
        # 1. MAINS GS-II: POLITY & CONSTITUTION -> FUNDAMENTAL RIGHTS
        # Detailed 14-microtopic breakdown as required
        # -------------------------------------------------------------
        fr_nodes = [
            KnowledgeNode(
                node_id="POL_FR_01_PHIL",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper II",
                subject="Indian Polity and Constitution",
                major_topic="Fundamental Rights",
                subtopic="Constitutional Philosophy & Nature",
                microtopic="Meaning, Philosophy, Negative vs Positive Obligations, Justiciability",
                prerequisites=[],
                connected_entries=["POL_DPSP_01", "POL_PREAMBLE_01"],
                relevant_pyqs=["PYQ_2020_PRE_FR_JUSTICIABLE"],
                required_depth=TopicDepth.FOUNDATION,
                keywords=["fundamental rights", "part iii", "justiciable", "magna carta", "constitutional philosophy", "negative liberty"],
                estimated_duration_min=15,
            ),
            KnowledgeNode(
                node_id="POL_FR_02_HIST",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper II",
                subject="Indian Polity and Constitution",
                major_topic="Fundamental Rights",
                subtopic="Historical Genesis & Evolution",
                microtopic="Historical Evolution: 1895 Constitution Bill, Nehru Report 1928, Karachi Resolution 1931, Sapru Committee",
                prerequisites=["POL_FR_01_PHIL"],
                connected_entries=["HIST_FREEDOM_STRUGGLE_01"],
                relevant_pyqs=["PYQ_2016_MAINS_NEHRU_REPORT"],
                required_depth=TopicDepth.CONCEPT,
                keywords=["nehru report 1928", "karachi resolution 1931", "sapru committee", "historical genesis", "constituent assembly debates"],
                estimated_duration_min=18,
            ),
            KnowledgeNode(
                node_id="POL_FR_03_ART12_13",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper II",
                subject="Indian Polity and Constitution",
                major_topic="Fundamental Rights",
                subtopic="Articles 12 & 13: Scope of State and Judicial Review",
                microtopic="Article 12 Definition of State, Article 13 Judicial Review, Doctrine of Eclipse, Severability, Waiver",
                prerequisites=["POL_FR_01_PHIL"],
                connected_entries=["POL_JUDICIARY_REVIEW_01"],
                relevant_pyqs=["PYQ_2019_PRE_ART12_STATE"],
                required_depth=TopicDepth.ANALYTICAL,
                keywords=["article 12", "definition of state", "article 13", "doctrine of eclipse", "severability", "judicial review", "r d shetty", "ajay hasia"],
                estimated_duration_min=22,
            ),
            KnowledgeNode(
                node_id="POL_FR_04_EQUALITY",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper II",
                subject="Indian Polity and Constitution",
                major_topic="Fundamental Rights",
                subtopic="Right to Equality (Articles 14–18)",
                microtopic="Equality before Law, Equal Protection of Laws, Non-discrimination (Art 15), Public Employment (Art 16), Untouchability (Art 17), Titles (Art 18)",
                prerequisites=["POL_FR_03_ART12_13"],
                connected_entries=["SOC_RESERVATION_01", "POL_AFFIRMATIVE_ACTION"],
                relevant_pyqs=["PYQ_2021_PRE_ART14_RULE_OF_LAW"],
                required_depth=TopicDepth.CONCEPT,
                keywords=["article 14", "article 15", "article 16", "article 17", "article 18", "rule of law", "reasonable classification", "indira sawhney"],
                estimated_duration_min=25,
            ),
            KnowledgeNode(
                node_id="POL_FR_05_FREEDOM",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper II",
                subject="Indian Polity and Constitution",
                major_topic="Fundamental Rights",
                subtopic="Right to Freedom (Articles 19–22)",
                microtopic="Six Freedoms (Art 19) & Reasonable Restrictions, Protection against Conviction (Art 20), Right to Life & Personal Liberty (Art 21), Preventive Detention (Art 22)",
                prerequisites=["POL_FR_03_ART12_13"],
                connected_entries=["POL_PRIVACY_PUTTASWAMY", "POL_CRIMINAL_JUSTICE"],
                relevant_pyqs=["PYQ_2017_MAINS_GS2_FED_1", "PYQ_2018_PRE_ART21_PRIVACY"],
                required_depth=TopicDepth.ANALYTICAL,
                keywords=["article 19", "reasonable restrictions", "article 20", "double jeopardy", "self-incrimination", "article 21", "maneka gandhi", "puttaswamy", "privacy", "article 22"],
                estimated_duration_min=30,
            ),
            KnowledgeNode(
                node_id="POL_FR_06_EXPLOITATION",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper II",
                subject="Indian Polity and Constitution",
                major_topic="Fundamental Rights",
                subtopic="Right against Exploitation (Articles 23–24)",
                microtopic="Prohibition of Traffic in Human Beings & Begar (Art 23), Child Labour Prohibition (Art 24), Bonded Labour",
                prerequisites=["POL_FR_01_PHIL"],
                connected_entries=["SOC_CHILD_RIGHTS_01"],
                relevant_pyqs=["PYQ_2017_PRE_ART24_CHILD_LABOUR"],
                required_depth=TopicDepth.CONCEPT,
                keywords=["article 23", "article 24", "traffic in human beings", "begar", "child labour", "bonded labour system"],
                estimated_duration_min=15,
            ),
            KnowledgeNode(
                node_id="POL_FR_07_RELIGION",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper II",
                subject="Indian Polity and Constitution",
                major_topic="Fundamental Rights",
                subtopic="Right to Freedom of Religion (Articles 25–28)",
                microtopic="Freedom of Conscience (Art 25), Religious Affairs Management (Art 26), Freedom from Taxes (Art 27), Religious Instruction (Art 28), Essential Religious Practices Test",
                prerequisites=["POL_FR_01_PHIL"],
                connected_entries=["POL_SECULARISM_01"],
                relevant_pyqs=["PYQ_2019_MAINS_ESSENTIAL_PRACTICE"],
                required_depth=TopicDepth.ANALYTICAL,
                keywords=["article 25", "article 26", "article 27", "article 28", "secularism", "essential religious practices", "sabarimala", "shirur mutt"],
                estimated_duration_min=22,
            ),
            KnowledgeNode(
                node_id="POL_FR_08_CULTURE_EDU",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper II",
                subject="Indian Polity and Constitution",
                major_topic="Fundamental Rights",
                subtopic="Cultural and Educational Rights (Articles 29–30)",
                microtopic="Protection of Interests of Minorities (Art 29), Right of Minorities to Establish Educational Institutions (Art 30), Scope of 'Minority'",
                prerequisites=["POL_FR_04_EQUALITY"],
                connected_entries=["SOC_MINORITY_WELFARE_01"],
                relevant_pyqs=["PYQ_2020_PRE_ART30_MINORITY"],
                required_depth=TopicDepth.CONCEPT,
                keywords=["article 29", "article 30", "minority educational institutions", "tma pai", "inspirational minority rights"],
                estimated_duration_min=18,
            ),
            KnowledgeNode(
                node_id="POL_FR_09_REMEDIES_ART32",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper II",
                subject="Indian Polity and Constitution",
                major_topic="Fundamental Rights",
                subtopic="Right to Constitutional Remedies (Article 32)",
                microtopic="Article 32 as 'Heart and Soul' of Constitution, Basic Structure status, Scope vs Article 226, Territorial Jurisdiction",
                prerequisites=["POL_FR_01_PHIL", "POL_FR_03_ART12_13"],
                connected_entries=["POL_JUDICIARY_SC_01"],
                relevant_pyqs=["PYQ_2018_PRE_ART32_HEART_SOUL"],
                required_depth=TopicDepth.CONCEPT,
                keywords=["article 32", "constitutional remedies", "dr ambedkar heart and soul", "basic structure", "article 226 vs 32"],
                estimated_duration_min=20,
            ),
            KnowledgeNode(
                node_id="POL_FR_10_WRITS",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper II",
                subject="Indian Polity and Constitution",
                major_topic="Fundamental Rights",
                subtopic="Writ Jurisdiction & Prerogative Orders",
                microtopic="Five Writs in Depth: Habeas Corpus, Mandamus, Prohibition, Certiorari, Quo-Warranto, Locus Standi & PIL Evolution",
                prerequisites=["POL_FR_09_REMEDIES_ART32"],
                connected_entries=["POL_PIL_EVOLUTION_01"],
                relevant_pyqs=["PYQ_2022_PRE_WRITS_QUO_WARRANTO"],
                required_depth=TopicDepth.ANALYTICAL,
                keywords=["habeas corpus", "mandamus", "prohibition", "certiorari", "quo-warranto", "public interest litigation", "locus standi"],
                estimated_duration_min=25,
            ),
            KnowledgeNode(
                node_id="POL_FR_11_RESTRICTIONS_33_35",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper II",
                subject="Indian Polity and Constitution",
                major_topic="Fundamental Rights",
                subtopic="Exceptions, Armed Forces & Martial Law (Articles 31A–35)",
                microtopic="Armed Forces Modifications (Art 33), Martial Law Indemnity (Art 34), Legislation to Give Effect to FRs (Art 35), Articles 31A, 31B, 31C",
                prerequisites=["POL_FR_03_ART12_13"],
                connected_entries=["POL_EMERGENCY_PROVISIONS_01"],
                relevant_pyqs=["PYQ_2019_PRE_ART33_ARMED_FORCES"],
                required_depth=TopicDepth.CONCEPT,
                keywords=["article 33", "article 34", "article 35", "article 31a", "article 31b", "article 31c", "martial law", "armed forces"],
                estimated_duration_min=18,
            ),
            KnowledgeNode(
                node_id="POL_FR_12_JUDGMENTS",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper II",
                subject="Indian Polity and Constitution",
                major_topic="Fundamental Rights",
                subtopic="Landmark Constitutional Precedents & Judicial Doctrines",
                microtopic="A.K. Gopalan, Shankari Prasad, Golaknath, Kesavananda Bharati (Basic Structure), Minerva Mills, Maneka Gandhi, K.S. Puttaswamy",
                prerequisites=["POL_FR_03_ART12_13", "POL_FR_05_FREEDOM"],
                connected_entries=["POL_BASIC_STRUCTURE_01"],
                relevant_pyqs=["PYQ_2020_MAINS_BASIC_STRUCTURE"],
                required_depth=TopicDepth.ANALYTICAL,
                keywords=["ak gopalan", "golaknath", "kesavananda bharati", "minerva mills", "maneka gandhi", "puttaswamy", "basic structure doctrine"],
                estimated_duration_min=30,
            ),
            KnowledgeNode(
                node_id="POL_FR_13_DEBATES",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper II",
                subject="Indian Polity and Constitution",
                major_topic="Fundamental Rights",
                subtopic="Contemporary Constitutional Debates & Controversies",
                microtopic="FR vs DPSP Primacy, Digital Surveillance, Hate Speech vs Free Expression, Sedition, Preventive Detention Debates, Substantive Equality",
                prerequisites=["POL_FR_04_EQUALITY", "POL_FR_05_FREEDOM", "POL_FR_12_JUDGMENTS"],
                connected_entries=["POL_CONTEMPORARY_DEBATES"],
                relevant_pyqs=["PYQ_2023_MAINS_FREE_SPEECH_INTERNET"],
                required_depth=TopicDepth.ANALYTICAL,
                keywords=["fr vs dpsp", "digital privacy", "hate speech", "sedition 124a", "surveillance", "proportionality test"],
                estimated_duration_min=25,
            ),
            KnowledgeNode(
                node_id="POL_FR_14_PYQ_MAINS",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper II",
                subject="Indian Polity and Constitution",
                major_topic="Fundamental Rights",
                subtopic="Prelims & Mains Answer Writing & PYQ Mastery",
                microtopic="PYQ Trend Analysis (2013-2025), Structure of Mains Answers, Common Prelims Traps, Fact-Matrix Memorisation",
                prerequisites=["POL_FR_04_EQUALITY", "POL_FR_05_FREEDOM", "POL_FR_10_WRITS", "POL_FR_12_JUDGMENTS"],
                connected_entries=["POL_ANSWER_WRITING_01"],
                relevant_pyqs=["PYQ_2017_MAINS_GS2_FED_1", "PYQ_2022_PRE_WRITS_QUO_WARRANTO"],
                required_depth=TopicDepth.APPLICATION_PYQ,
                keywords=["pyq mastery", "prelims elimination techniques", "mains 250 words framework", "constitutional answer writing"],
                estimated_duration_min=20,
            ),
        ]
        for n in fr_nodes:
            self.add_node(n)

        # -------------------------------------------------------------
        # 2. PRELIMS GS PAPER I: CORE TOPICS
        # -------------------------------------------------------------
        prelims_nodes = [
            KnowledgeNode(
                node_id="PRE_HIST_INDUS",
                stage=UPSCStage.PRELIMS,
                paper="Prelims GS Paper I",
                subject="Ancient Indian History",
                major_topic="Ancient India",
                subtopic="Indus Valley Civilisation",
                microtopic="Town planning, drainage system, major sites (Harappa, Mohenjodaro, Dholavira, Lothal), economy and trade",
                prerequisites=[],
                keywords=["indus valley", "harappa", "dholavira", "lothal", "town planning", "bronze age"],
                estimated_duration_min=15,
            ),
            KnowledgeNode(
                node_id="PRE_HIST_VEDIC",
                stage=UPSCStage.PRELIMS,
                paper="Prelims GS Paper I",
                subject="Ancient Indian History",
                major_topic="Ancient India",
                subtopic="Vedic Age & Mahajanapadas",
                microtopic="Early vs Later Vedic society, literature (Vedas, Upanishads), rise of 16 Mahajanapadas, Magadha dominance",
                prerequisites=["PRE_HIST_INDUS"],
                keywords=["rigveda", "later vedic", "mahajanapadas", "magadha", "upanishads"],
                estimated_duration_min=15,
            ),
            KnowledgeNode(
                node_id="PRE_GEOG_MONSOON",
                stage=UPSCStage.PRELIMS,
                paper="Prelims GS Paper I",
                subject="Geography",
                major_topic="Physical & Indian Geography",
                subtopic="Indian Monsoon Mechanism",
                microtopic="Differential heating, ITCZ shift, Somali jet, Tibetan heating, El Nino, La Nina, Indian Ocean Dipole",
                prerequisites=[],
                keywords=["monsoon", "itcz", "jet stream", "el nino", "iod", "somali jet", "southwest monsoon"],
                estimated_duration_min=20,
            ),
            KnowledgeNode(
                node_id="PRE_ECON_MONETARY",
                stage=UPSCStage.PRELIMS,
                paper="Prelims GS Paper I",
                subject="Economy and Social Development",
                major_topic="Money & Banking",
                subtopic="Monetary Policy & RBI Operations",
                microtopic="Repo, Reverse Repo, SDF, MSF, CRR, SLR, Open Market Operations, Monetary Policy Committee (MPC)",
                prerequisites=[],
                keywords=["rbi", "repo rate", "monetary policy committee", "crr", "slr", "open market operations"],
                estimated_duration_min=20,
            ),
            KnowledgeNode(
                node_id="PRE_ENV_BIODIVERSITY",
                stage=UPSCStage.PRELIMS,
                paper="Prelims GS Paper I",
                subject="Environment and Ecology",
                major_topic="Biodiversity & Conservation",
                subtopic="Protected Areas & International Conventions",
                microtopic="National Parks, Wildlife Sanctuaries, Biosphere Reserves, Ramsar Sites, IUCN Red List categories",
                prerequisites=[],
                keywords=["national park", "wildlife sanctuary", "biosphere reserve", "ramsar", "iucn", "project tiger"],
                estimated_duration_min=20,
            ),
            KnowledgeNode(
                node_id="PRE_SCI_BIOTECH",
                stage=UPSCStage.PRELIMS,
                paper="Prelims GS Paper I",
                subject="Science and Technology",
                major_topic="Biotechnology",
                subtopic="Genetics & Vaccines",
                microtopic="DNA/RNA vaccines, CRISPR-Cas9 gene editing, recombinant DNA, stem cell applications",
                prerequisites=[],
                keywords=["crispr", "gene editing", "mrna vaccine", "stem cell", "biotechnology", "dna"],
                estimated_duration_min=15,
            ),
        ]
        for n in prelims_nodes:
            self.add_node(n)

        # -------------------------------------------------------------
        # 3. PRELIMS CSAT PAPER II
        # -------------------------------------------------------------
        csat_nodes = [
            KnowledgeNode(
                node_id="CSAT_READING_COMP",
                stage=UPSCStage.PRELIMS,
                paper="Prelims CSAT Paper II",
                subject="General Mental Ability",
                major_topic="Reading Comprehension",
                subtopic="Inference, Assumption & Core Message",
                microtopic="Deducing primary assumptions, logical corollaries, most rational inferences, avoiding extreme options",
                prerequisites=[],
                keywords=["csat", "reading comprehension", "logical corollary", "assumption", "crux", "inference"],
                estimated_duration_min=20,
            ),
            KnowledgeNode(
                node_id="CSAT_NUM_PERCENTAGES",
                stage=UPSCStage.PRELIMS,
                paper="Prelims CSAT Paper II",
                subject="General Mental Ability",
                major_topic="Basic Numeracy",
                subtopic="Percentages, Profit-Loss & Ratio",
                microtopic="Successive percentage change, cost-price calculations, ratio-proportion, mixture problems",
                prerequisites=[],
                keywords=["percentage", "profit and loss", "ratio", "csat numeracy", "fractions"],
                estimated_duration_min=18,
            ),
        ]
        for n in csat_nodes:
            self.add_node(n)

        # -------------------------------------------------------------
        # 4. MAINS GS-I: HISTORY, GEOGRAPHY & SOCIETY
        # -------------------------------------------------------------
        gs1_nodes = [
            KnowledgeNode(
                node_id="GS1_HIST_1857",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper I",
                subject="Modern Indian History",
                major_topic="Freedom Struggle",
                subtopic="Revolt of 1857 & Early Nationalism",
                microtopic="Causes (political, economic, socio-religious), nature, limitations, Government of India Act 1858 impact",
                prerequisites=[],
                keywords=["1857 revolt", "sepoy mutiny", "queen victoria proclamation", "act of 1858"],
                estimated_duration_min=20,
            ),
            KnowledgeNode(
                node_id="GS1_SOC_SECULARISM",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper I",
                subject="Indian Society",
                major_topic="Social Issues",
                subtopic="Indian vs Western Secularism",
                microtopic="Principled distance, sarva dharma sambhava, communalism vs secularism, challenges to pluralism",
                prerequisites=[],
                keywords=["indian secularism", "western secularism", "principled distance", "sarva dharma sambhava", "communalism"],
                estimated_duration_min=22,
            ),
        ]
        for n in gs1_nodes:
            self.add_node(n)

        # -------------------------------------------------------------
        # 5. MAINS GS-III: ECONOMY, ENVIRONMENT, S&T, SECURITY
        # -------------------------------------------------------------
        gs3_nodes = [
            KnowledgeNode(
                node_id="GS3_ECON_INCLUSIVE_GROWTH",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper III",
                subject="Indian Economy",
                major_topic="Growth & Development",
                subtopic="Inclusive Growth & Jobless Growth",
                microtopic="Measurement of inequality (Gini, Palma ratio), employment generation, structural transformation bottlenecks",
                prerequisites=["PRE_ECON_MONETARY"],
                keywords=["inclusive growth", "jobless growth", "gini coefficient", "structural transformation", "labour market"],
                estimated_duration_min=22,
            ),
            KnowledgeNode(
                node_id="GS3_ENV_CLIMATE_ACTION",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper III",
                subject="Environment and Ecology",
                major_topic="Climate Change Governance",
                subtopic="India's Panchamrit & Net Zero Commitments",
                microtopic="COP26 Glasgow pledges, NDC targets, renewable transition, carbon pricing, adaptation financing",
                prerequisites=["PRE_ENV_BIODIVERSITY"],
                keywords=["panchamrit", "net zero 2070", "ndc targets", "cop26", "cop28", "renewable energy transition"],
                estimated_duration_min=22,
            ),
            KnowledgeNode(
                node_id="GS3_SEC_BORDER_MGMT",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper III",
                subject="Internal Security",
                major_topic="Border Management",
                subtopic="Cross-Border Infiltration & Smart Fencing",
                microtopic="CIBMS technology, border terrain challenges (LoC, LAC, Indo-Myanmar, Indo-Bangladesh), drug & arms smuggling",
                prerequisites=[],
                keywords=["border management", "cibms", "smart fencing", "cross-border terrorism", "loc", "lac"],
                estimated_duration_min=20,
            ),
        ]
        for n in gs3_nodes:
            self.add_node(n)

        # -------------------------------------------------------------
        # 6. MAINS GS-IV: ETHICS, INTEGRITY & APTITUDE
        # -------------------------------------------------------------
        gs4_nodes = [
            KnowledgeNode(
                node_id="GS4_ETHICS_FOUNDATIONS",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper IV",
                subject="Ethics, Integrity and Aptitude",
                major_topic="Ethics and Human Interface",
                subtopic="Essence, Determinants & Consequences of Ethics",
                microtopic="Deontological vs Consequentialist ethics, ethical dilemmas in administration, emotional intelligence",
                prerequisites=[],
                keywords=["ethics determinants", "deontology", "utilitarianism", "kant", "ethical dilemma", "emotional intelligence"],
                estimated_duration_min=25,
            ),
            KnowledgeNode(
                node_id="GS4_CORP_GOVERNANCE",
                stage=UPSCStage.MAINS,
                paper="Mains GS Paper IV",
                subject="Ethics, Integrity and Aptitude",
                major_topic="Probity in Governance",
                subtopic="Corporate Governance & Public Integrity",
                microtopic="Moral integrity vs professional efficiency, conflict of interest, whistleblowing protection",
                prerequisites=["GS4_ETHICS_FOUNDATIONS"],
                relevant_pyqs=["PYQ_2022_MAINS_GS4_ETHICS"],
                keywords=["corporate governance", "moral integrity", "whistleblower", "conflict of interest"],
                estimated_duration_min=20,
            ),
        ]
        for n in gs4_nodes:
            self.add_node(n)

        # -------------------------------------------------------------
        # 7. MAINS ESSAY
        # -------------------------------------------------------------
        essay_nodes = [
            KnowledgeNode(
                node_id="ESSAY_PHILOSOPHICAL",
                stage=UPSCStage.ESSAY,
                paper="Mains Essay",
                subject="Essay Writing",
                major_topic="Philosophical & Reflective Essays",
                subtopic="Deconstructing Philosophical Prompts",
                microtopic="Brainstorming multidimensional angles (historical, social, political, economic, ethical, international), thesis statement drafting",
                prerequisites=[],
                keywords=["essay writing", "philosophical essay", "multidimensional analysis", "thesis statement"],
                estimated_duration_min=25,
            ),
        ]
        for n in essay_nodes:
            self.add_node(n)

        # -------------------------------------------------------------
        # 8. OPTIONAL SUBJECTS (MODULAR EXPANSION)
        # -------------------------------------------------------------
        optional_nodes = [
            KnowledgeNode(
                node_id="OPT_PSIR_WESTERN_THINKERS",
                stage=UPSCStage.OPTIONAL,
                paper="Optional Paper I & II",
                subject="PSIR Optional",
                major_topic="Western Political Thought",
                subtopic="Plato, Aristotle & Machiavelli",
                microtopic="Theory of Forms, Philosopher King, Aristotelian constitutionalism, Machiavellian political realism",
                prerequisites=[],
                keywords=["plato", "aristotle", "machiavelli", "psir optional", "western political thought"],
                estimated_duration_min=30,
            ),
        ]
        for n in optional_nodes:
            self.add_node(n)

        # -------------------------------------------------------------
        # 9. INTERVIEW & PERSONALITY TEST
        # -------------------------------------------------------------
        interview_nodes = [
            KnowledgeNode(
                node_id="INTV_DAF_ANALYSIS",
                stage=UPSCStage.INTERVIEW,
                paper="Interview / Personality Test",
                subject="Personality Test",
                major_topic="Detailed Application Form (DAF)",
                subtopic="Home State, Hobbies & Educational Background",
                microtopic="Anticipating DAF questions, handling situational dilemmas, balanced articulation, state socioeconomic profiles",
                prerequisites=[],
                keywords=["upsc interview", "daf preparation", "personality test", "situational questions", "mock interview"],
                estimated_duration_min=25,
            ),
        ]
        for n in interview_nodes:
            self.add_node(n)

        # -------------------------------------------------------------
        # 10. CURRENT AFFAIRS ANCHOR
        # -------------------------------------------------------------
        ca_nodes = [
            KnowledgeNode(
                node_id="CA_CONSTITUTIONAL_2026",
                stage=UPSCStage.CURRENT_AFFAIRS,
                paper="Current Affairs",
                subject="Current Affairs",
                major_topic="Constitutional Developments 2025-2026",
                subtopic="Recent Supreme Court Constitution Benches",
                microtopic="Sub-classification of SC/STs judgment, Electoral Bonds verdict follow-up, Governor's assent powers",
                prerequisites=["POL_FR_04_EQUALITY", "POL_FR_12_JUDGMENTS"],
                keywords=["sub-classification sc st", "electoral bonds", "article 200 governor assent", "current affairs 2026"],
                estimated_duration_min=20,
            ),
        ]
        for n in ca_nodes:
            self.add_node(n)
