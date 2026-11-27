"""Security controls and prompt injection guards for untrusted research documents.

Treats all external documents, uploaded notes, and web content as untrusted input.
Prevents prompt injection, system override attempts, and malicious directives.
Enforces safe parsing: never executes external scripts, shell code, or binaries.
"""
from __future__ import annotations

import re
from typing import Any

# Known prompt injection, delimiter breakout, and adversarial instruction patterns
ADVERSARIAL_INJECTION_PATTERNS = [
    r"(?i)\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions\b",
    r"(?i)\bdisregard\s+(?:all\s+)?(?:previous|prior|above)\s+instructions\b",
    r"(?i)\bforget\s+(?:all\s+)?(?:previous|prior|above)\s+instructions\b",
    r"(?i)\byou\s+are\s+now\s+(?:a|an|the)\b",
    r"(?i)\bsystem\s+override\b",
    r"(?i)\bdeveloper\s+mode\b",
    r"(?i)\bDAN\s+mode\b",
    r"(?i)\bmark\s+(?:all\s+)?(?:claims|status)\s+(?:as\s+)?verified\b",
    r"(?i)\bbypass\s+(?:all\s+)?(?:verification|fact[\s-]check|quality|qa)\b",
    r"(?i)\boverride\s+(?:verification|status|gates|policy)\b",
    r"<\|(?:im_start|im_end|system|user|assistant)\|>",
    r"\[\/?(?:INST|SYS)\]",
    r"<<SYS>>",
    r"---BEGIN INSTRUCTION---",
    r"(?i)\bdo\s+not\s+verify\b",
    r"(?i)\bassume\s+(?:this|everything)\s+is\s+true\b",
]

# Patterns for potential command injection or script execution in text
CODE_EXECUTION_PATTERNS = [
    r"(?i)\b(?:eval|exec|os\.system|subprocess\.Popen)\s*\(",
    r"(?i)\brm\s+-rf\b",
    r"(?i)\b(?:powershell|cmd\.exe|bash|sh)\s+-[a-zA-Z]",
    r"`[^`]+`",  # backtick shell interpolation
]


class ResearchSecurityError(ValueError):
    """Raised when malicious or adversarial content is detected in untrusted inputs."""
    pass


class ResearchSecurityGuard:
    """Sanitizes untrusted documents and detects adversarial prompt injections."""

    @classmethod
    def scan_for_threats(cls, text: str) -> list[str]:
        """Scan untrusted text for adversarial prompt injection or code execution tokens."""
        if not text:
            return []
        
        detected_threats: list[str] = []
        for pattern in ADVERSARIAL_INJECTION_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                detected_threats.append(f"Prompt injection pattern detected: '{matches[0]}'")

        for pattern in CODE_EXECUTION_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                detected_threats.append(f"Potential code execution syntax detected: '{matches[0]}'")

        return detected_threats

    @classmethod
    def sanitize_untrusted_text(cls, text: str, raise_on_threat: bool = False) -> str:
        """Sanitize untrusted text by neutralizing control tokens and injection markers.
        
        If raise_on_threat is True, raises ResearchSecurityError when threats are detected.
        Otherwise, strips or neutralizes the offending tokens and returns safe text.
        """
        if not text:
            return ""

        threats = cls.scan_for_threats(text)
        if threats and raise_on_threat:
            raise ResearchSecurityError(f"Security threat detected in untrusted document: {'; '.join(threats)}")

        sanitized = text
        # Neutralize template delimiters and prompt injection markers
        for pattern in ADVERSARIAL_INJECTION_PATTERNS:
            sanitized = re.sub(pattern, "[FILTERED_ADVERSARIAL_INSTRUCTION]", sanitized)

        # Neutralize code execution directives
        for pattern in CODE_EXECUTION_PATTERNS:
            sanitized = re.sub(pattern, "[FILTERED_CODE_EXECUTION]", sanitized)

        # Strip null bytes and non-printable control characters (except common whitespace)
        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", sanitized)

        return sanitized

    @classmethod
    def validate_safe_for_evidence(cls, text: str) -> tuple[bool, str]:
        """Check if text is safe to be ingested as research evidence or notes."""
        threats = cls.scan_for_threats(text)
        if threats:
            return False, f"Document contains {len(threats)} adversarial or unsafe pattern(s): {threats[0]}"
        return True, "SAFE"
