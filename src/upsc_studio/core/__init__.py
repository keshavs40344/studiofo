"""Core package for configuration, hardware detection, paths, errors, and logging."""

from upsc_studio.core.errors import ErrorCategory, ClassifiedError, classify_error, ProductionError

__all__ = ["ErrorCategory", "ClassifiedError", "classify_error", "ProductionError"]

