"""Universal Knowledge and Documentary Intelligence Engine.

Provides deep domain ontologies, pedagogical narrative arcs, visual recommendations,
and fact-checking rules across 6 major universal knowledge domains for General Knowledge,
Current Affairs, and Deep Dive educational documentaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class UniversalDomain(str, Enum):
    """The 6 universal knowledge and documentary domains."""
    SCIENCE_AND_TECH = "SCIENCE_AND_TECH"
    HISTORY_AND_WORLD = "HISTORY_AND_WORLD"
    GEOGRAPHY_AND_EARTH = "GEOGRAPHY_AND_EARTH"
    ECONOMY_AND_INDUSTRY = "ECONOMY_AND_INDUSTRY"
    CONSTITUTION_AND_LAW = "CONSTITUTION_AND_LAW"
    PHILOSOPHY_AND_THOUGHT = "PHILOSOPHY_AND_THOUGHT"


@dataclass(frozen=True)
class DomainSpecialistProfile:
    """Rich domain specialist metadata, pedagogical guidelines, and visual rules."""
    domain: UniversalDomain
    display_name: str
    focus_areas: tuple[str, ...]
    pedagogical_arc: tuple[str, ...]
    recommended_visuals: tuple[str, ...]
    fact_checking_hierarchy: str
    common_misconceptions: tuple[str, ...]
    preferred_tone: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain.value,
            "display_name": self.display_name,
            "focus_areas": list(self.focus_areas),
            "pedagogical_arc": list(self.pedagogical_arc),
            "recommended_visuals": list(self.recommended_visuals),
            "fact_checking_hierarchy": self.fact_checking_hierarchy,
            "common_misconceptions": list(self.common_misconceptions),
            "preferred_tone": self.preferred_tone,
            "metadata": self.metadata,
        }


DOMAIN_PROFILES: dict[UniversalDomain, DomainSpecialistProfile] = {
    UniversalDomain.SCIENCE_AND_TECH: DomainSpecialistProfile(
        domain=UniversalDomain.SCIENCE_AND_TECH,
        display_name="Science & Technology Specialist",
        focus_areas=(
            "Space exploration and astronomy",
            "Quantum computing and semiconductors",
            "Biotechnology and genomics",
            "Renewable energy and nuclear physics",
            "Artificial intelligence and robotics",
            "Medical technology and immunology",
        ),
        pedagogical_arc=(
            "Genesis: The scientific problem and physical laws governing the phenomenon",
            "Mechanism: Step-by-step physical, chemical, or algorithmic process",
            "Empirical Evidence: Experimental verification, benchmark data, and observed measurements",
            "Limitations & Edge Cases: Thermodynamics boundaries, noise, and ethical constraints",
            "Frontier Outlook: Next-generation prototypes and open research questions",
        ),
        recommended_visuals=(
            "process_animation",
            "scientific_illustration",
            "data_chart",
            "flowchart",
            "annotated_diagram",
        ),
        fact_checking_hierarchy="Peer-reviewed journals (Nature/Science/IEEE), national research labs, space agencies (ISRO/NASA), patent filings.",
        common_misconceptions=(
            "Conflating theoretical hypotheses with experimentally verified laws",
            "Assuming 100% efficiency without thermodynamic entropy losses",
            "Overstating AI capabilities beyond probabilistic model parameters",
        ),
        preferred_tone="Rigorous, empirical, accessible, first-principles explanatory",
    ),
    UniversalDomain.HISTORY_AND_WORLD: DomainSpecialistProfile(
        domain=UniversalDomain.HISTORY_AND_WORLD,
        display_name="History & Global Affairs Specialist",
        focus_areas=(
            "Ancient, medieval, and modern civilizations",
            "Anti-colonial struggles and national movements",
            "Geopolitical conflicts and military strategies",
            "Diplomatic treaties and international alliances",
            "Social revolutions and institutional evolution",
            "Cold War dynamics and contemporary multipolarity",
        ),
        pedagogical_arc=(
            "Genesis & Antecedents: Sociopolitical preconditions and catalytic triggers",
            "Unfolding Sequence: Chronological turning points, strategic decisions, and key actors",
            "Documentary Evidence: Primary treaties, official communiqués, and archival correspondence",
            "Historiographical Debates: Diverse scholarly interpretations and counter-narratives",
            "Legacy & Modern Ramifications: Lasting borders, constitutional echoes, and current geopolitical impacts",
        ),
        recommended_visuals=(
            "historical_timeline",
            "geographical_map",
            "institutional_diagram",
            "split_comparison",
            "annotated_document",
        ),
        fact_checking_hierarchy="National archives, official state communiqués, primary treaties, peer-reviewed historical scholarship.",
        common_misconceptions=(
            "Attributing complex historical movements solely to single individuals ('Great Man' fallacy)",
            "Projecting modern values retrospectively onto historical contexts (anachronism)",
            "Confusing propaganda pamphlets with verified archival records",
        ),
        preferred_tone="Objective, contextual, analytical, multi-perspective documentary",
    ),
    UniversalDomain.GEOGRAPHY_AND_EARTH: DomainSpecialistProfile(
        domain=UniversalDomain.GEOGRAPHY_AND_EARTH,
        display_name="Earth Systems & Geography Specialist",
        focus_areas=(
            "Geomorphology and plate tectonics",
            "Climatology, monsoons, and atmospheric circulation",
            "Oceanography and thermohaline currents",
            "Biogeography, ecosystems, and biodiversity hotspots",
            "Resource distribution and critical mineral geology",
            "Anthropogenic climate change and disaster resilience",
        ),
        pedagogical_arc=(
            "Physical Basis: Lithospheric, atmospheric, or hydrological boundary conditions",
            "Dynamic Process: Thermodynamic gradients, pressure systems, and tectonic forces",
            "Spatial Distribution: Continental patterns, geographic zones, and GIS coordinates",
            "Human-Environment Interaction: Resource utilization, vulnerability, and ecological impact",
            "Mitigation & Sustainable Management: Geotechnical adaptations and ecological conservation",
        ),
        recommended_visuals=(
            "geographical_map",
            "process_animation",
            "data_chart",
            "scientific_illustration",
            "annotated_diagram",
        ),
        fact_checking_hierarchy="Geological surveys, meteorological organizations (IMD/WMO), IPCC assessments, satellite remote sensing data.",
        common_misconceptions=(
            "Treating climate and weather as interchangeable terms",
            "Assuming tectonic activity occurs uniformly rather than at plate boundaries",
            "Ignoring Coriolis effect and pressure gradients in wind circulation",
        ),
        preferred_tone="Spatial, data-driven, ecological, system-thinking",
    ),
    UniversalDomain.ECONOMY_AND_INDUSTRY: DomainSpecialistProfile(
        domain=UniversalDomain.ECONOMY_AND_INDUSTRY,
        display_name="Economics & Industry Specialist",
        focus_areas=(
            "Macroeconomic indicators and fiscal policy",
            "Monetary mechanisms and central banking",
            "Global trade corridors and supply chains",
            "Industrial transitions and infrastructure development",
            "Agricultural markets and food security",
            "Financial institutions and capital flows",
        ),
        pedagogical_arc=(
            "Economic Premise: Resource scarcity, incentives, and structural conditions",
            "Market Mechanism: Supply-demand equilibrium, interest rate transmission, or multiplier effect",
            "Empirical Trends: Historical time series, trade balances, and GDP share datasets",
            "Structural Bottlenecks: Inflationary pressures, debt vulnerabilities, and market distortions",
            "Policy Horizon: Institutional reforms, investment frameworks, and sustainable growth strategies",
        ),
        recommended_visuals=(
            "data_chart",
            "flowchart",
            "split_comparison",
            "process_animation",
            "institutional_diagram",
        ),
        fact_checking_hierarchy="Central bank reports (RBI/Federal Reserve), National Statistics Offices, Economic Survey, WTO/IMF/World Bank data.",
        common_misconceptions=(
            "Confusing money creation with wealth generation",
            "Assuming inflation has a single mono-causal origin rather than demand-pull/cost-push dynamics",
            "Equating trade deficits with national economic loss without analyzing capital accounts",
        ),
        preferred_tone="Analytical, balanced, data-grounded, policy-focused",
    ),
    UniversalDomain.CONSTITUTION_AND_LAW: DomainSpecialistProfile(
        domain=UniversalDomain.CONSTITUTION_AND_LAW,
        display_name="Law & Constitutional Governance Specialist",
        focus_areas=(
            "Constitutional philosophy and doctrine",
            "Separation of powers and checks and balances",
            "Judicial review and landmark judicial precedents",
            "Legislative procedures and statutory interpretation",
            "Administrative accountability and anti-corruption frameworks",
            "Comparative constitutionalism and human rights law",
        ),
        pedagogical_arc=(
            "Constitutional Foundation: Founding debates, constitutional articles, and legal preamble",
            "Statutory Framework: Statutory provisions, institutional mandates, and procedural rules",
            "Judicial Precedents: Ratio decidendi, obiter dicta, and evolving judicial doctrines",
            "Institutional Friction: Executive overreach, legislative delays, or federal conflicts",
            "Reform Pathway: Law commission recommendations and democratic safeguards",
        ),
        recommended_visuals=(
            "institutional_diagram",
            "split_comparison",
            "annotated_document",
            "historical_timeline",
            "flowchart",
        ),
        fact_checking_hierarchy="Official constitutional texts, Supreme Court/High Court law reports, legislative acts, parliamentary records.",
        common_misconceptions=(
            "Confusing judicial obiter dicta with binding ratio decidendi",
            "Assuming constitutional conventions have no legal significance",
            "Overlooking legislative procedure and delegated legislation nuances",
        ),
        preferred_tone="Precise, jurisprudential, principled, democratic",
    ),
    UniversalDomain.PHILOSOPHY_AND_THOUGHT: DomainSpecialistProfile(
        domain=UniversalDomain.PHILOSOPHY_AND_THOUGHT,
        display_name="Philosophy & Social Thought Specialist",
        focus_areas=(
            "Moral philosophy and normative ethics (deontology, utilitarianism, virtue)",
            "Epistemology and theories of knowledge",
            "Political philosophy (justice, liberty, equality, sovereignty)",
            "Eastern and Indian philosophical traditions (Nyaya, Buddhist logic, Advaita)",
            "Social philosophy and critical sociology",
            "Ethics of modern technology and existential risk",
        ),
        pedagogical_arc=(
            "Fundamental Question: The underlying existential, moral, or epistemological dilemma",
            "Conceptual Structure: Definitions of core terms, logical premises, and deductions",
            "Thought Experiments & Classic Case Studies: Real-world analogies testing the limits of the theory",
            "Critiques & Dialectics: Counter-arguments from rival philosophical traditions",
            "Contemporary Application: Applying the philosophical framework to modern ethical decisions",
        ),
        recommended_visuals=(
            "split_comparison",
            "flowchart",
            "annotated_diagram",
            "historical_timeline",
            "institutional_diagram",
        ),
        fact_checking_hierarchy="Canonical primary philosophical texts, academic peer-reviewed philosophy journals (Mind/Ethics), Oxford/Stanford Ency.",
        common_misconceptions=(
            "Reducing utilitarianism to crude hedonism without rule-based qualitative distinctions",
            "Equating moral relativism with moral nihilism",
            "Conflating formal logical validity with empirical truth",
        ),
        preferred_tone="Reflective, dialectical, intellectually honest, probing",
    ),
}


class UniversalKnowledgeEngine:
    """Classifies content into universal domains and generates structured documentary guides."""

    DOMAIN_KEYWORDS: dict[UniversalDomain, tuple[str, ...]] = {
        UniversalDomain.SCIENCE_AND_TECH: (
            "space", "quantum", "semiconductor", "biotech", "gene", "crispr", "energy",
            "nuclear", "algorithm", "artificial intelligence", "robotics", "physics",
            "chemistry", "biology", "vaccine", "pathogen", "telescope", "satellite", "isro",
            "nasa", "superconductor", "nanotech", "photosynthesis", "cellular", "dna",
        ),
        UniversalDomain.HISTORY_AND_WORLD: (
            "war", "empire", "civilization", "dynasty", "revolution", "treaty", "allies",
            "cold war", "independence", "colony", "battle", "crusade", "medieval", "ancient",
            "monarchy", "treaty of", "rebellion", "renaissance", "ottoman", "mughal", "british",
            "chola", "maurya", "world war", "geopolitics", "diplomacy", "partition",
        ),
        UniversalDomain.GEOGRAPHY_AND_EARTH: (
            "monsoon", "plate tectonics", "earthquake", "volcano", "river", "ocean", "cyclone",
            "atmosphere", "glacier", "climate change", "desert", "soil", "ecosystem", "biome",
            "lithosphere", "troposphere", "drainage basin", "el nino", "la nina", "himalaya",
            "coriolis", "sedimentary", "trench", "forest", "coral reef",
        ),
        UniversalDomain.ECONOMY_AND_INDUSTRY: (
            "inflation", "gdp", "fiscal", "monetary policy", "interest rate", "rbi", "imf",
            "banking", "supply chain", "trade", "wto", "deficit", "tax", "industry",
            "manufacturing", "agriculture", "currency", "stock market", "debt", "tariff",
            "infrastructure", "labor", "export", "import", "capital",
        ),
        UniversalDomain.CONSTITUTION_AND_LAW: (
            "constitution", "fundamental rights", "supreme court", "high court", "writs",
            "parliament", "judiciary", "article", "habeas corpus", "separation of powers",
            "federalism", "judicial review", "basic structure", "legislation", "ordinance",
            "governor", "president", "citizenship", "amendment", "statute", "criminal law",
        ),
        UniversalDomain.PHILOSOPHY_AND_THOUGHT: (
            "ethics", "moral", "justice", "utilitarianism", "deontology", "virtue", "liberty",
            "equality", "epistemology", "philosophy", "logic", "dialectic", "buddhist", "nyaya",
            "kant", "aristotle", "plato", "rationalism", "empiricism", "social contract",
        ),
    }

    def detect_domain(
        self,
        chapter_title: str,
        content_category: str = "general_knowledge",
        notes_text: str = "",
    ) -> UniversalDomain:
        """Infer the primary knowledge domain using weighted keyword scoring."""
        text = f"{chapter_title} {notes_text[:2000]}".lower()

        scores: dict[UniversalDomain, int] = {domain: 0 for domain in UniversalDomain}

        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if re.search(rf"\b{re.escape(kw)}\b", text):
                    # Title matches weigh 3x higher than body text matches
                    if re.search(rf"\b{re.escape(kw)}\b", chapter_title.lower()):
                        scores[domain] += 3
                    else:
                        scores[domain] += 1

        # Fallback category heuristics
        if content_category == "current_affairs" and scores[UniversalDomain.ECONOMY_AND_INDUSTRY] == 0:
            scores[UniversalDomain.HISTORY_AND_WORLD] += 1

        best_domain = max(scores, key=scores.get)
        if scores[best_domain] == 0:
            # Default fallback domain based on category
            if content_category == "deep_dive":
                return UniversalDomain.SCIENCE_AND_TECH
            if content_category == "current_affairs":
                return UniversalDomain.HISTORY_AND_WORLD
            return UniversalDomain.GEOGRAPHY_AND_EARTH

        return best_domain

    def select_domain_profile(
        self,
        chapter_title: str,
        content_category: str = "general_knowledge",
        notes_text: str = "",
    ) -> tuple[str, dict[str, Any]]:
        """Return the specialist identifier and comprehensive profile dictionary."""
        domain = self.detect_domain(chapter_title, content_category, notes_text)
        profile = DOMAIN_PROFILES[domain]
        profile_key = f"{domain.value}_SPECIALIST"

        profile_data = profile.to_dict()
        profile_data["content_category"] = content_category
        profile_data["exam_syllabus_mapping"] = "NOT_APPLICABLE" if content_category != "upsc" else "OPTIONAL_ENRICHMENT"
        profile_data["source_review_required"] = True

        return profile_key, profile_data

    def generate_pedagogical_outline(
        self,
        domain: UniversalDomain,
        chapter_title: str,
        target_duration_min: int = 30,
    ) -> list[dict[str, Any]]:
        """Construct a 5-phase educational outline adhering to the domain pedagogical arc."""
        profile = DOMAIN_PROFILES[domain]
        arc_steps = profile.pedagogical_arc
        visuals = profile.recommended_visuals

        durations_sec = [
            round(target_duration_min * 60 * 0.15),  # 15% Genesis
            round(target_duration_min * 60 * 0.35),  # 35% Mechanism
            round(target_duration_min * 60 * 0.25),  # 25% Empirical Case Studies
            round(target_duration_min * 60 * 0.15),  # 15% Misconceptions/Debates
            round(target_duration_min * 60 * 0.10),  # 10% Outlook
        ]

        sections = []
        phase_names = [
            "Genesis & Conceptual Problem",
            "Fundamental Mechanism & Process",
            "Empirical Evidence & Key Case Studies",
            "Counter-Perspectives & Misconceptions",
            "Contemporary Significance & Frontiers",
        ]

        for i, (name, arc, dur) in enumerate(zip(phase_names, arc_steps, durations_sec), start=1):
            sec_id = f"SEC_{i:02d}"
            assigned_visual = visuals[(i - 1) % len(visuals)]
            sections.append({
                "section_id": sec_id,
                "title": f"{chapter_title}: {name}",
                "pedagogical_role": arc,
                "target_duration_sec": dur,
                "visual_category": assigned_visual,
                "learning_objective": f"Understand {name.lower()} in {chapter_title}.",
                "domain": domain.value,
            })

        return sections
