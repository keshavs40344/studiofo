"""Universal Content Categories: Dynamic domain registry across UPSC, GK, Current Affairs, and Deep-Dive Documentaries."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class ContentPillar(str, Enum):
    UPSC_AND_CIVIL_SERVICES = "UPSC_AND_CIVIL_SERVICES"
    GENERAL_KNOWLEDGE = "GENERAL_KNOWLEDGE"
    CURRENT_AFFAIRS = "CURRENT_AFFAIRS"
    DEEP_DIVE_DOCUMENTARY = "DEEP_DIVE_DOCUMENTARY"


@dataclass
class SubcategoryDefinition:
    subcategory_id: str
    pillar: ContentPillar
    name: str
    description: str
    default_visual_style: str
    primary_source_types: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["pillar"] = self.pillar.value
        return d


class CategoryRegistry:
    """Dynamic domain registry that supports seamless addition of new categories without code changes."""

    def __init__(self, config_file: Optional[Path] = None) -> None:
        self.config_file = config_file
        self._categories: dict[str, SubcategoryDefinition] = {}
        self._init_default_categories()
        if config_file and config_file.exists():
            self.load_from_json(config_file)

    def register_subcategory(self, subcat: SubcategoryDefinition) -> None:
        self._categories[subcat.subcategory_id] = subcat

    def get_subcategory(self, subcat_id: str) -> Optional[SubcategoryDefinition]:
        return self._categories.get(subcat_id)

    def list_by_pillar(self, pillar: ContentPillar) -> list[SubcategoryDefinition]:
        return [c for c in self._categories.values() if c.pillar == pillar]

    def list_all(self) -> list[SubcategoryDefinition]:
        return list(self._categories.values())

    def detect_category(self, title: str, description: str = "") -> SubcategoryDefinition:
        """Infer best-matching subcategory using keyword mapping."""
        text = f"{title} {description}".lower()
        best_cat: Optional[SubcategoryDefinition] = None
        best_score = -1

        for cat in self._categories.values():
            score = 0
            if cat.name.lower() in text:
                score += 5
            for tag in cat.tags:
                if tag.lower() in text:
                    score += 2
            if score > best_score:
                best_score = score
                best_cat = cat

        return best_cat or self._categories.get(
            "UPSC_POLITY", list(self._categories.values())[0]
        )

    def load_from_json(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data.get("subcategories", []):
            self.register_subcategory(
                SubcategoryDefinition(
                    subcategory_id=item["subcategory_id"],
                    pillar=ContentPillar(item["pillar"]),
                    name=item["name"],
                    description=item["description"],
                    default_visual_style=item.get("default_visual_style", "Conceptual Diagram"),
                    primary_source_types=item.get("primary_source_types", []),
                    tags=item.get("tags", []),
                )
            )

    def export_to_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "subcategories": [c.to_dict() for c in self._categories.values()]
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _init_default_categories(self) -> None:
        defaults = [
            # A. UPSC AND CIVIL SERVICES
            SubcategoryDefinition(
                subcategory_id="UPSC_POLITY",
                pillar=ContentPillar.UPSC_AND_CIVIL_SERVICES,
                name="Indian Polity and Constitution",
                description="Constitutional provisions, Parliament, Judiciary, Writs, Governance, Federalism.",
                default_visual_style="Constitutional Diagram / Judicial Hierarchy",
                primary_source_types=["PRIMARY_OFFICIAL", "JUDICIAL_VERDICT", "STATUTE"],
                tags=["polity", "constitution", "article", "amendment", "supreme court", "parliament", "fundamental rights", "writs"],
            ),
            SubcategoryDefinition(
                subcategory_id="UPSC_HISTORY",
                pillar=ContentPillar.UPSC_AND_CIVIL_SERVICES,
                name="Modern & Ancient Indian History",
                description="Freedom struggle, national movement, ancient civilizations, socio-religious movements.",
                default_visual_style="Animated Timeline / Historical Maps",
                primary_source_types=["PRIMARY_OFFICIAL", "ACADEMIC_PEER_REVIEWED"],
                tags=["history", "modern history", "freedom struggle", "gandhi", "1857", "nehru report", "ancient india", "vedic"],
            ),
            SubcategoryDefinition(
                subcategory_id="UPSC_GEOGRAPHY",
                pillar=ContentPillar.UPSC_AND_CIVIL_SERVICES,
                name="Indian and World Geography",
                description="Physical geography, monsoon mechanisms, river systems, climatology, economic geography.",
                default_visual_style="Topographical & Dynamic GIS Map",
                primary_source_types=["PRIMARY_OFFICIAL", "METEOROLOGICAL_DATA"],
                tags=["geography", "monsoon", "plate tectonics", "river", "climate", "el nino", "soil"],
            ),
            SubcategoryDefinition(
                subcategory_id="UPSC_ECONOMY",
                pillar=ContentPillar.UPSC_AND_CIVIL_SERVICES,
                name="Indian Economy and Monetary Policy",
                description="Macroeconomics, fiscal deficit, inflation, RBI operations, inclusive growth, trade.",
                default_visual_style="Economic Flowchart / Supply-Demand Vector Charts",
                primary_source_types=["PRIMARY_OFFICIAL", "STATUTORY_REGULATOR"],
                tags=["economy", "rbi", "gdp", "inflation", "monetary policy", "fiscal policy", "banking", "inclusive growth"],
            ),
            SubcategoryDefinition(
                subcategory_id="UPSC_ENVIRONMENT",
                pillar=ContentPillar.UPSC_AND_CIVIL_SERVICES,
                name="Environment, Biodiversity and Climate Change",
                description="Ecology, national parks, international climate treaties (UNFCCC, COP), conservation.",
                default_visual_style="Ecological Biosphere / Climate Impact Graphic",
                primary_source_types=["PRIMARY_OFFICIAL", "INTERNATIONAL_TREATY"],
                tags=["environment", "biodiversity", "climate change", "panchamrit", "cop28", "ramsar", "iucn"],
            ),
            SubcategoryDefinition(
                subcategory_id="UPSC_ETHICS",
                pillar=ContentPillar.UPSC_AND_CIVIL_SERVICES,
                name="Ethics, Integrity and Aptitude",
                description="Moral philosophy, public probity, emotional intelligence, conflict of interest, case studies.",
                default_visual_style="Ethical Dilemma Dialectical Matrix",
                primary_source_types=["ACADEMIC_PEER_REVIEWED", "ADMINISTRATIVE_REFORM_COMMISSION"],
                tags=["ethics", "integrity", "probity", "moral philosophy", "deontology", "emotional intelligence", "corporate governance"],
            ),

            # B. GENERAL KNOWLEDGE & SCIENCE
            SubcategoryDefinition(
                subcategory_id="GK_BRAIN_NEUROSCIENCE",
                pillar=ContentPillar.GENERAL_KNOWLEDGE,
                name="Human Brain, Cognitive Science & Biology",
                description="How the human brain processes information, neural synapses, memory encoding, cognitive science.",
                default_visual_style="3D Neural Network / Cellular Biological Process",
                primary_source_types=["ACADEMIC_PEER_REVIEWED", "SCIENTIFIC_JOURNAL"],
                tags=["brain", "neuroscience", "neural", "synapse", "cognitive", "memory", "biology", "human body", "information processing"],
            ),
            SubcategoryDefinition(
                subcategory_id="GK_SPACE_ASTRONOMY",
                pillar=ContentPillar.GENERAL_KNOWLEDGE,
                name="Space, Astronomy and Astrophysics",
                description="Planetary systems, black holes, space exploration missions, James Webb Telescope, cosmology.",
                default_visual_style="Astrophysical Simulation / Orbital Mechanics Diagram",
                primary_source_types=["SCIENTIFIC_JOURNAL", "SPACE_AGENCY_OFFICIAL"],
                tags=["space", "astronomy", "isro", "nasa", "black hole", "cosmology", "james webb", "orbit", "planetary"],
            ),
            SubcategoryDefinition(
                subcategory_id="GK_AI_COMPUTING",
                pillar=ContentPillar.GENERAL_KNOWLEDGE,
                name="Artificial Intelligence and Computer Systems",
                description="Machine learning, neural architectures, microprocessors, quantum computing, digital evolution.",
                default_visual_style="Computational Architecture / Data Flow Pipeline",
                primary_source_types=["ACADEMIC_PEER_REVIEWED", "TECHNICAL_SPECIFICATION"],
                tags=["artificial intelligence", "machine learning", "computer science", "quantum computing", "algorithm", "llm"],
            ),
            SubcategoryDefinition(
                subcategory_id="GK_WORLD_HISTORY",
                pillar=ContentPillar.GENERAL_KNOWLEDGE,
                name="World History and Civilizations",
                description="Renaissance, Industrial Revolution, World Wars, major global treaties, civilizational rise and fall.",
                default_visual_style="Global Chronological Timeline / Territorial Evolution Map",
                primary_source_types=["HISTORICAL_DOCUMENT", "ACADEMIC_PEER_REVIEWED"],
                tags=["world history", "industrial revolution", "world war", "civilization", "renaissance", "cold war"],
            ),

            # C. CURRENT AFFAIRS
            SubcategoryDefinition(
                subcategory_id="CA_NATIONAL_POLICY",
                pillar=ContentPillar.CURRENT_AFFAIRS,
                name="National Governance and Public Policy Developments",
                description="Recent legislative acts, government welfare missions, statutory guidelines, electoral reforms.",
                default_visual_style="Policy Pipeline / Stakeholder Impact Matrix",
                primary_source_types=["PRIMARY_OFFICIAL", "PARLIAMENTARY_RECORD", "GAZETTE_OF_INDIA"],
                tags=["current affairs", "policy", "cabinet decision", "welfare scheme", "bill", "act", "election commission"],
            ),
            SubcategoryDefinition(
                subcategory_id="CA_JUDICIARY_DEVELOPMENTS",
                pillar=ContentPillar.CURRENT_AFFAIRS,
                name="Supreme Court Constitution Benches & Legal Precedents",
                description="Recent landmark judgments, legal doctrine evolution, constitutional interpretation updates.",
                default_visual_style="Case Law Precedent Comparison / Constitutional Benchmark",
                primary_source_types=["JUDICIAL_VERDICT", "OFFICIAL_COURT_RECORD"],
                tags=["supreme court", "constitution bench", "judgment", "verdict", "high court", "legal development", "cji"],
            ),
            SubcategoryDefinition(
                subcategory_id="CA_INTERNATIONAL_GEOPOLITICS",
                pillar=ContentPillar.CURRENT_AFFAIRS,
                name="International Geopolitics & Global Summits",
                description="Bilateral treaties, multilateral summits (G20, BRICS, UN), geopolitical conflicts and diplomacy.",
                default_visual_style="Geopolitical Influence Map / Bilateral Treaty Flow",
                primary_source_types=["INTERNATIONAL_ORGANIZATION", "DIPLOMATIC_COMMUNIQUE"],
                tags=["geopolitics", "international affairs", "brics", "g20", "united nations", "treaty", "conflict", "diplomacy"],
            ),

            # D. DEEP-DIVE DOCUMENTARIES
            SubcategoryDefinition(
                subcategory_id="DEEP_DIVE_COMPREHENSIVE",
                pillar=ContentPillar.DEEP_DIVE_DOCUMENTARY,
                name="Extensive Epoch & System Deep-Dives",
                description="Multi-chapter connected documentary explaining complex systems from historical root to modern frontier.",
                default_visual_style="Documentary Multi-Tier Cinematic Graphics",
                primary_source_types=["PRIMARY_OFFICIAL", "ACADEMIC_PEER_REVIEWED", "OFFICIAL_ARCHIVE"],
                tags=["deep dive", "documentary series", "comprehensive analysis", "root to frontier", "system analysis"],
            ),
        ]
        for sub in defaults:
            self.register_subcategory(sub)
