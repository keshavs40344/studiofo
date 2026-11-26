"""Mains answer-writing intelligence: directive word parsing and structured frameworks."""

from __future__ import annotations

DIRECTIVE_RULES = {
    "critically examine": {
        "demand": "Probe both merits/achievements and limitations/counterarguments objectively, then conclude with balanced reforms.",
        "required_sections": ["Core Context", "Supporting Arguments / Strengths", "Limitations & Criticisms", "Way Forward & Balanced Conclusion"],
    },
    "discuss": {
        "demand": "Explore multiple dimensions (constitutional, institutional, socio-economic) with reasons and examples.",
        "required_sections": ["Definition & Context", "Multi-Dimensional Analysis", "Challenges", "Way Forward"],
    },
    "analyse": {
        "demand": "Break the issue into constituent parts, explain cause-effect mechanisms, and assess implications.",
        "required_sections": ["Core Concept", "Causal Mechanism Breakdown", "Implications", "Synthesis"],
    },
    "evaluate": {
        "demand": "Assess effectiveness against stated objectives using evidence, data, or judicial benchmarks.",
        "required_sections": ["Objective Benchmark", "Measured Achievements", "Gaps / Shortcomings", "Overall Assessment"],
    },
    "elucidate": {
        "demand": "Clarify and explain the statement clearly with concrete examples and institutional illustrations.",
        "required_sections": ["Meaning & Clarification", "Mechanism / Illustration", "Real-World Examples", "Conclusion"],
    },
}


class MainsAnswerAnalyzer:
    """Parses UPSC Mains questions and generates directive-aligned answer frameworks."""

    @staticmethod
    def detect_directive(question: str) -> tuple[str, dict]:
        q_lower = question.lower()
        for directive, rule in DIRECTIVE_RULES.items():
            if directive in q_lower:
                return directive, rule
        return "discuss", DIRECTIVE_RULES["discuss"]

    def build_framework(self, question: str, chapter_title: str, specialist_profile: dict) -> dict:
        """Create a question-specific Mains answer framework."""
        directive, rule = self.detect_directive(question)
        return {
            "question": question,
            "chapter_title": chapter_title,
            "label": "EDUCATIONAL_EXAMPLE_NOT_OFFICIAL_UPSC_ANSWER",
            "directive_word": directive.upper(),
            "directive_demand": rule["demand"],
            "introduction_approach": f"Define '{chapter_title}' concisely with its constitutional/institutional or empirical anchor.",
            "body_structure": rule["required_sections"],
            "relevant_dimensions": specialist_profile.get("mains_dimensions", []),
            "key_terminology_to_use": specialist_profile.get("key_terminology", []),
            "recommended_examples": specialist_profile.get("examples", []),
            "conclusion_approach": "Conclude with a forward-looking, evidence-backed institutional reform or balanced synthesis.",
        }
