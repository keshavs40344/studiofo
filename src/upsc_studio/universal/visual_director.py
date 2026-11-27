"""Universal Visual Director: Domain-specific visual explanations, dynamic kinematics, and misconception prevention."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class VisualArchetype(str, Enum):
    HISTORICAL_TIMELINE = "HISTORICAL_TIMELINE"
    TERRITORIAL_MAP = "TERRITORIAL_MAP"
    CONSTITUTIONAL_HIERARCHY = "CONSTITUTIONAL_HIERARCHY"
    ECONOMIC_FLOW = "ECONOMIC_FLOW"
    SCIENTIFIC_SIMULATION = "SCIENTIFIC_SIMULATION"
    NEURAL_CELLULAR_PROCESS = "NEURAL_CELLULAR_PROCESS"
    POLICY_FLOWCHART = "POLICY_FLOWCHART"
    CASE_LAW_LADDER = "CASE_LAW_LADDER"
    SPLIT_COMPARISON = "SPLIT_COMPARISON"
    DIALECTICAL_DEBATE_SCALE = "DIALECTICAL_DEBATE_SCALE"


@dataclass
class VisualExplanationSpec:
    scene_id: str
    archetype: VisualArchetype
    visual_summary: str            # What the viewer sees
    on_screen_dynamics: str        # What changes on screen dynamically
    narration_alignment: str       # What the narrator explains
    conceptual_relationship: str   # What relationship visual demonstrates (cause-effect, hierarchy, balance)
    misconception_prevented: str   # What misconception this visual actively prevents
    illustrative_label: str        # Explicit illustrative / source marking
    motion_duration_sec: float = 6.0
    primary_elements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["archetype"] = self.archetype.value
        return d


class UniversalVisualDirector:
    """Plans and validates purpose-built visual explanations across science, history, polity, and current affairs."""

    def plan_visual_for_concept(
        self,
        scene_id: str,
        concept_title: str,
        domain_category: str,
        narration_text: str,
    ) -> VisualExplanationSpec:
        cat_lower = domain_category.lower()

        # 1. Science & Biology / Brain
        if "brain" in cat_lower or "neuro" in cat_lower or "science" in cat_lower:
            return VisualExplanationSpec(
                scene_id=scene_id,
                archetype=VisualArchetype.NEURAL_CELLULAR_PROCESS,
                visual_summary="Cross-section diagram of neuron, showing voltage changes along myelinated axon and neurotransmitter exocytosis at the synaptic cleft.",
                on_screen_dynamics="Action potential wavefront travels left-to-right; voltage graph dips to -70mV, spikes to +30mV; vesicle fusion releases colored neurotransmitter dots across synaptic gap.",
                narration_alignment=f"Narrator explains {concept_title} and electrochemical transmission mechanism.",
                conceptual_relationship="Demonstrates physical conversion of electrical voltage into chemical messenger molecules across synapses.",
                misconception_prevented="Prevents the misconception that electrical signals jump directly across biological neurons without chemical mediation.",
                illustrative_label="ILLUSTRATIVE SCIENTIFIC MODEL: Hodgkin-Huxley & Synaptic Cleft Biophysics",
                motion_duration_sec=7.0,
                primary_elements=["Neuron Soma", "Axon Hillock", "Nodes of Ranvier", "Synaptic Vesicles", "Neurotransmitter Receptors"],
            )

        # 2. History
        if "history" in cat_lower:
            return VisualExplanationSpec(
                scene_id=scene_id,
                archetype=VisualArchetype.HISTORICAL_TIMELINE,
                visual_summary="Interactive chronological timeline showing major milestone anchors with side-by-side territorial map change.",
                on_screen_dynamics="Timeline pointer scrubs forward through dates; territory boundaries highlight and expand; key primary document quotes slide into focus.",
                narration_alignment=f"Narrator narrates the historical evolution of {concept_title}.",
                conceptual_relationship="Establishes exact cause-and-effect progression from historical catalyst to modern institution.",
                misconception_prevented="Prevents anachronistic interpretation by anchoring decisions in their contemporary historical context.",
                illustrative_label="HISTORICAL CARTOGRAPHY & ARCHIVE CHRONOLOGY",
                motion_duration_sec=8.0,
                primary_elements=["Chronological Axis", "Primary Source Extract", "Boundary Shift Overlay"],
            )

        # 3. Economy
        if "economy" in cat_lower:
            return VisualExplanationSpec(
                scene_id=scene_id,
                archetype=VisualArchetype.ECONOMIC_FLOW,
                visual_summary="Animated circular flow diagram connecting Central Bank, Commercial Banking System, Household Depositors, and Corporate Borrowers.",
                on_screen_dynamics="Policy rate dial turns up; liquidity streams contract; borrowing cost bar chart rises; consumer demand indicator cools.",
                narration_alignment=f"Narrator explains monetary policy transmission for {concept_title}.",
                conceptual_relationship="Demonstrates monetary transmission mechanism from interest rate changes to price stability.",
                misconception_prevented="Prevents the misconception that central bank rates immediately change consumer retail prices overnight.",
                illustrative_label="ECONOMIC FLOW & TRANSMISSION SIMULATION",
                motion_duration_sec=6.5,
                primary_elements=["RBI / Central Bank Node", "Repo Rate Lever", "Liquidity Stream Vectors", "Inflation Thermometer"],
            )

        # 4. Current Affairs / Judicial Bench
        if "current" in cat_lower or "policy" in cat_lower or "judiciary" in cat_lower:
            return VisualExplanationSpec(
                scene_id=scene_id,
                archetype=VisualArchetype.CASE_LAW_LADDER,
                visual_summary="Split-screen matrix comparing petitioner arguments, state justification, and Constitution Bench verdict with majority/dissent breakdown.",
                on_screen_dynamics="Majority ratio decidendi box illuminates in gold; dissenting perspectives highlighted in blue; key operative paragraphs highlighted.",
                narration_alignment=f"Narrator analyzes the legal doctrine and constitutional ruling in {concept_title}.",
                conceptual_relationship="Clarifies the legal boundary between binding ratio decidendi and non-binding obiter dicta.",
                misconception_prevented="Prevents the misconception that bench observations in courtroom hearings are part of the final binding judgment.",
                illustrative_label="OFFICIAL JUDICIAL ANALYSIS: Supreme Court Constitution Bench",
                motion_duration_sec=7.0,
                primary_elements=["Bench Composition", "Constitutional Articles", "Ratio Decidendi", "Dissenting Opinion"],
            )

        # 5. Default: Polity / Governance
        return VisualExplanationSpec(
            scene_id=scene_id,
            archetype=VisualArchetype.CONSTITUTIONAL_HIERARCHY,
            visual_summary="Multi-tier constitutional architecture showing Fundamental Rights guarantees acting as enforceable boundary conditions on State power.",
            on_screen_dynamics="State authority arrows attempt expansion; constitutional boundary wall activates; judicial review writ arrows restore individual liberty.",
            narration_alignment=f"Narrator explains checks and balances for {concept_title}.",
            conceptual_relationship="Visualizes negative obligations: constitutional boundaries actively restrict arbitrary state exercise of power.",
            misconception_prevented="Prevents the misconception that Fundamental Rights are mere policy aspirations rather than justiciable guarantees.",
            illustrative_label="CONSTITUTIONAL CHECKS & BALANCES ARCHITECTURE",
            motion_duration_sec=6.5,
            primary_elements=["Individual Liberty Sanctuary", "State Executive Vector", "Articles 12-13 Boundary", "Article 32 Writ Shield"],
        )

    def get_domain_visual_guidelines(self, topic_title: str) -> dict[str, Any]:
        """Derive visual archetype guidelines and motion parameters for a topic."""
        spec = self.plan_visual_for_concept(
            scene_id="GUIDELINE_SCENE",
            concept_title=topic_title,
            domain_category=topic_title,
            narration_text=topic_title,
        )
        return {
            "topic_title": topic_title,
            "recommended_archetype": spec.archetype.value,
            "visual_summary": spec.visual_summary,
            "on_screen_dynamics": spec.on_screen_dynamics,
            "illustrative_label": spec.illustrative_label,
            "primary_elements": spec.primary_elements,
            "misconception_prevented": spec.misconception_prevented,
            "motion_duration_sec": spec.motion_duration_sec,
        }
