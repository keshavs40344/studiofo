"""Safe document text extraction and atomic claim decomposition.

Extracts text from local documents/notes, splits them into addressable
page/section blocks, and derives atomic factual claims with exact supporting excerpts.
Applies security filtering to protect against prompt injection in untrusted inputs.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Optional

from bs4 import BeautifulSoup

from upsc_studio.research.security import ResearchSecurityGuard

HIGH_IMPACT_PATTERNS = (
    r"\barticle\s+\d+[a-z]?\b",
    r"\bsection\s+\d+[a-z]?\b",
    r"\bschedule\s+(?:[ivx]+|\d+)\b",
    r"\b\d+(?:\.\d+)?\s*%",
    r"\b(?:19|20)\d{2}\b",
    r"\b(?:act|amendment|judgment|committee|commission|scheme|budget|rank|ordinance|treaty)\b",
)


@dataclass
class DocumentSection:
    section_id: str
    section_title: str
    page_or_section: str
    char_start: int
    char_end: int
    clean_text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AtomicClaimCandidate:
    statement: str
    page_or_section: str
    supporting_excerpt: str
    ref_period: Optional[str] = None
    is_high_impact: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DocumentExtractor:
    """Safely extracts text and decomposes documents into atomic verifiable propositions."""

    def __init__(self, security_guard: type[ResearchSecurityGuard] = ResearchSecurityGuard) -> None:
        self.security = security_guard

    def extract_clean_text(self, raw_content: str, content_type: str = "text/plain") -> str:
        """Extract clean text, neutralizing any malicious control or prompt injection tokens."""
        if not raw_content:
            return ""

        if "html" in content_type.lower():
            soup = BeautifulSoup(raw_content, "html.parser")
            # Remove scripts, styles, forms
            for tag in soup(["script", "style", "noscript", "meta", "iframe"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
        else:
            text = raw_content

        # Sanitize against prompt injections and malicious instructions
        clean = self.security.sanitize_untrusted_text(text, raise_on_threat=False)
        # Normalize whitespace while preserving line structure
        lines = [line.strip() for line in clean.splitlines() if line.strip()]
        return "\n".join(lines)

    def chunk_into_sections(self, text: str, default_page_label: str = "Section") -> list[DocumentSection]:
        """Divide text into addressable sections based on headers or paragraphs."""
        clean_text = self.extract_clean_text(text)
        if not clean_text:
            return []

        # Split on headers (# Heading) or double newlines
        parts = re.split(r"(?m)(?=^#{1,4}\s+)", clean_text)
        sections: list[DocumentSection] = []
        current_offset = 0

        for idx, part in enumerate(parts, 1):
            part = part.strip()
            if not part:
                continue

            lines = part.splitlines()
            first_line = lines[0].lstrip("#").strip() if lines else f"Part {idx}"
            title = first_line[:80] if first_line else f"Section {idx}"
            page_or_sec = f"{default_page_label} {idx} ({title})"

            sec_len = len(part)
            sections.append(
                DocumentSection(
                    section_id=f"SEC_{idx:02d}",
                    section_title=title,
                    page_or_section=page_or_sec,
                    char_start=current_offset,
                    char_end=current_offset + sec_len,
                    clean_text=part,
                )
            )
            current_offset += sec_len + 1

        return sections

    def extract_atomic_claims(
        self,
        text: str,
        page_or_section: str = "Page 1",
    ) -> list[AtomicClaimCandidate]:
        """Decompose text into discrete atomic claims with supporting excerpts."""
        clean_text = self.extract_clean_text(text)
        if not clean_text:
            return []

        # Split into individual sentences
        raw_sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+|\n+", clean_text)
            if len(s.strip()) >= 15
        ]

        candidates: list[AtomicClaimCandidate] = []
        for sentence in raw_sentences:
            low = sentence.lower()
            is_high_impact = any(re.search(pat, low) for pat in HIGH_IMPACT_PATTERNS)

            # Check if sentence has year or reference period
            year_match = re.search(r"\b(?:19|20)\d{2}\b", sentence)
            ref_period = year_match.group(0) if year_match else None

            # For long compound sentences with conjunctions, extract atomic propositions
            clauses = self._split_into_atomic_propositions(sentence)
            for clause in clauses:
                if len(clause) < 15:
                    continue
                candidates.append(
                    AtomicClaimCandidate(
                        statement=clause,
                        page_or_section=page_or_section,
                        supporting_excerpt=sentence[:300],  # Sentence provides surrounding context
                        ref_period=ref_period,
                        is_high_impact=is_high_impact,
                    )
                )

        return candidates

    def _split_into_atomic_propositions(self, sentence: str) -> list[str]:
        """Break down a compound sentence into atomic propositions if semicolon or 'while' is used."""
        # Simple rule: if contains semicolons, split
        if ";" in sentence:
            parts = [p.strip() for p in sentence.split(";") if len(p.strip()) >= 15]
            if len(parts) > 1:
                return parts
        return [sentence]
