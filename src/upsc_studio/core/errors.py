"""Production error classification, taxonomy and retry policies.

Enforces a 10-category error taxonomy to prevent endless retries of permanent failures
and guarantee fail-closed behavior for academic, rights and publication gates.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ErrorCategory(str, Enum):
    """The 10 standard production error categories."""
    TRANSIENT_EXTERNAL = "TRANSIENT_EXTERNAL"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    INVALID_USER_INPUT = "INVALID_USER_INPUT"
    RESEARCH_VALIDATION_FAILURE = "RESEARCH_VALIDATION_FAILURE"
    ACADEMIC_QUALITY_FAILURE = "ACADEMIC_QUALITY_FAILURE"
    RIGHTS_FAILURE = "RIGHTS_FAILURE"
    AUDIO_VIDEO_FAILURE = "AUDIO_VIDEO_FAILURE"
    FILESYSTEM_FAILURE = "FILESYSTEM_FAILURE"
    DATABASE_FAILURE = "DATABASE_FAILURE"
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"


@dataclass(frozen=True)
class ClassifiedError:
    """Structured, actionable classification of a failure."""
    category: ErrorCategory
    message: str
    original_type: str
    is_retryable: bool
    requires_human_review: bool
    recovery_suggestion: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "message": self.message,
            "original_type": self.original_type,
            "is_retryable": self.is_retryable,
            "requires_human_review": self.requires_human_review,
            "recovery_suggestion": self.recovery_suggestion,
            "details": self.details,
        }


class ProductionError(Exception):
    """Base class for domain-specific classified errors."""
    category: ErrorCategory = ErrorCategory.TRANSIENT_EXTERNAL
    is_retryable: bool = False
    requires_human_review: bool = True
    recovery_suggestion: str = "Inspect project logs."

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TransientExternalError(ProductionError):
    category = ErrorCategory.TRANSIENT_EXTERNAL
    is_retryable = True
    requires_human_review = False
    recovery_suggestion = "Wait for network/external service recovery and retry."


class MissingDependencyError(ProductionError):
    category = ErrorCategory.MISSING_DEPENDENCY
    is_retryable = False
    requires_human_review = True
    recovery_suggestion = "Install the missing system dependency or external tool."


class InvalidUserInputError(ProductionError):
    category = ErrorCategory.INVALID_USER_INPUT
    is_retryable = False
    requires_human_review = True
    recovery_suggestion = "Correct user input parameters, notes, or uploaded files."


class ResearchValidationError(ProductionError):
    category = ErrorCategory.RESEARCH_VALIDATION_FAILURE
    is_retryable = False
    requires_human_review = True
    recovery_suggestion = "Review claims against official primary sources; resolve contradictions."


class AcademicQualityError(ProductionError):
    category = ErrorCategory.ACADEMIC_QUALITY_FAILURE
    is_retryable = False
    requires_human_review = True
    recovery_suggestion = "Expand syllabus coverage or address prerequisite conceptual gaps."


class RightsFailureError(ProductionError):
    category = ErrorCategory.RIGHTS_FAILURE
    is_retryable = False
    requires_human_review = True
    recovery_suggestion = "Provide verified license or replace unverified media asset."


class AudioVideoFailureError(ProductionError):
    category = ErrorCategory.AUDIO_VIDEO_FAILURE
    is_retryable = False
    requires_human_review = True
    recovery_suggestion = "Re-record audio, fix subtitle timing, or re-render video."


class FilesystemFailureError(ProductionError):
    category = ErrorCategory.FILESYSTEM_FAILURE
    is_retryable = False
    requires_human_review = True
    recovery_suggestion = "Free disk space or verify filesystem read/write permissions."


class DatabaseFailureError(ProductionError):
    category = ErrorCategory.DATABASE_FAILURE
    is_retryable = False
    requires_human_review = True
    recovery_suggestion = "Check SQLite database lock, run PRAGMA integrity_check, or repair schema."


class AuthenticationFailureError(ProductionError):
    category = ErrorCategory.AUTHENTICATION_FAILURE
    is_retryable = False
    requires_human_review = True
    recovery_suggestion = "Re-authenticate OAuth credentials or refresh expired API tokens."


def classify_error(exc: Exception) -> ClassifiedError:
    """Classify any exception into the standard 10-category production error taxonomy."""
    msg = str(exc)
    exc_type = type(exc).__name__
    msg_lower = msg.lower()

    # 1. Domain production errors with explicit taxonomy
    if isinstance(exc, ProductionError):
        return ClassifiedError(
            category=exc.category,
            message=msg,
            original_type=exc_type,
            is_retryable=exc.is_retryable,
            requires_human_review=exc.requires_human_review,
            recovery_suggestion=exc.recovery_suggestion,
            details=exc.details,
        )

    # 2. Database failures (SQLite specific)
    if isinstance(exc, (sqlite3.OperationalError, sqlite3.DatabaseError, sqlite3.IntegrityError)):
        is_lock = "locked" in msg_lower or "busy" in msg_lower
        return ClassifiedError(
            category=ErrorCategory.DATABASE_FAILURE,
            message=msg,
            original_type=exc_type,
            is_retryable=is_lock,  # Database lock is transiently retryable with backoff
            requires_human_review=not is_lock,
            recovery_suggestion="Retry after lock release or run PRAGMA integrity_check." if is_lock else "Resolve foreign key or schema violation.",
            details={"sqlite_error": True, "locked": is_lock},
        )

    # 3. Missing dependencies
    dependency_tools = [r"ffmpeg", r"ffprobe", r"piper", r"tesseract", r"qgis", r"inkscape"]
    dependency_failure_hints = [r"not found", r"missing", r"executable not found", r"command not found", r"no module named", r"model not installed", r"not installed"]
    if any(re.search(tool, msg_lower) for tool in dependency_tools) and any(re.search(hint, msg_lower) for hint in dependency_failure_hints):
        return ClassifiedError(
            category=ErrorCategory.MISSING_DEPENDENCY,
            message=msg,
            original_type=exc_type,
            is_retryable=False,
            requires_human_review=True,
            recovery_suggestion="Ensure external dependency (FFmpeg, Piper, etc.) is installed on system PATH.",
        )

    # 4. Filesystem failures (disk space, permissions, IO)
    if isinstance(exc, (PermissionError, IsADirectoryError, NotADirectoryError)) or "no space left" in msg_lower or "disk full" in msg_lower or "insufficient disk space" in msg_lower:
        return ClassifiedError(
            category=ErrorCategory.FILESYSTEM_FAILURE,
            message=msg,
            original_type=exc_type,
            is_retryable=False,
            requires_human_review=True,
            recovery_suggestion="Verify disk space (>1GB) and folder permissions.",
        )

    # 5. Transient external failures (network, timeout, connection drop)
    transient_patterns = [r"timeout", r"timed out", r"connection refused", r"connection reset", r"econnreset", r"503", r"429", r"temporary failure"]
    if isinstance(exc, (TimeoutError, ConnectionError)) or any(re.search(pat, msg_lower) for pat in transient_patterns):
        return ClassifiedError(
            category=ErrorCategory.TRANSIENT_EXTERNAL,
            message=msg,
            original_type=exc_type,
            is_retryable=True,
            requires_human_review=False,
            recovery_suggestion="Transient network/API interruption. Automatic retry with backoff is safe.",
        )

    # 6. Authentication / OAuth / Credentials
    auth_patterns = [r"oauth", r"token expired", r"unauthorized", r"authentication", r"client_secrets", r"401", r"403 forbidden"]
    if any(re.search(pat, msg_lower) for pat in auth_patterns):
        return ClassifiedError(
            category=ErrorCategory.AUTHENTICATION_FAILURE,
            message=msg,
            original_type=exc_type,
            is_retryable=False,
            requires_human_review=True,
            recovery_suggestion="Re-authorize Google/YouTube OAuth or update API keys.",
        )

    # 7. Research validation failures (prompt injection, contradictions, unverified claims)
    research_patterns = [r"prompt injection", r"adversarial", r"contradiction", r"unverified claim", r"cutoff date", r"unsupported high-impact"]
    if any(re.search(pat, msg_lower) for pat in research_patterns):
        return ClassifiedError(
            category=ErrorCategory.RESEARCH_VALIDATION_FAILURE,
            message=msg,
            original_type=exc_type,
            is_retryable=False,
            requires_human_review=True,
            recovery_suggestion="Resolve factual contradictions or remove adversarial prompt injection from source materials.",
        )

    # 8. Academic quality failures
    academic_patterns = [r"syllabus", r"learning objective", r"prerequisite gap", r"coverage matrix", r"incomplete chapter"]
    if any(re.search(pat, msg_lower) for pat in academic_patterns):
        return ClassifiedError(
            category=ErrorCategory.ACADEMIC_QUALITY_FAILURE,
            message=msg,
            original_type=exc_type,
            is_retryable=False,
            requires_human_review=True,
            recovery_suggestion="Expand lesson content to fulfill missing syllabus subtopics and prerequisites.",
        )

    # 9. Rights / Copyright failures
    rights_patterns = [r"copyright", r"unverified license", r"license", r"fair use", r"asset rights", r"rights ledger"]
    if any(re.search(pat, msg_lower) for pat in rights_patterns):
        return ClassifiedError(
            category=ErrorCategory.RIGHTS_FAILURE,
            message=msg,
            original_type=exc_type,
            is_retryable=False,
            requires_human_review=True,
            recovery_suggestion="Replace unverified third-party asset or provide license proof.",
        )

    # 10. Audio / Video failures
    media_patterns = [r"audio", r"clipping", r"dead air", r"silence", r"render", r"codec", r"subtitle", r"wav", r"mp4", r"resample"]
    if any(re.search(pat, msg_lower) for pat in media_patterns):
        return ClassifiedError(
            category=ErrorCategory.AUDIO_VIDEO_FAILURE,
            message=msg,
            original_type=exc_type,
            is_retryable=False,
            requires_human_review=True,
            recovery_suggestion="Inspect audio recording quality, fix subtitle syntax, or verify video dimensions.",
        )

    # 11. User input errors
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return ClassifiedError(
            category=ErrorCategory.INVALID_USER_INPUT,
            message=msg,
            original_type=exc_type,
            is_retryable=False,
            requires_human_review=True,
            recovery_suggestion="Verify requested configuration, parameters, and supplied inputs.",
        )

    # Default fallback
    return ClassifiedError(
        category=ErrorCategory.INVALID_USER_INPUT,
        message=msg,
        original_type=exc_type,
        is_retryable=False,
        requires_human_review=True,
        recovery_suggestion="Review task logs and inspect error details.",
    )
