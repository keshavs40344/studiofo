"""Safe file-path validation, hashing, and workspace directory helpers."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_PROJECTS_DIR = PROJECT_ROOT / "projects"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "upsc_studio.db"


def sanitize_slug(name: str, max_len: int = 60) -> str:
    """Convert an arbitrary name into a safe filesystem slug."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip()).strip("_").lower()
    return (cleaned[:max_len] or "untitled")


def ensure_within_base(base_dir: Path, target_path: Path) -> Path:
    """Resolve target_path and verify it does not escape base_dir."""
    base_resolved = base_dir.resolve()
    target_resolved = target_path.resolve()
    if target_resolved != base_resolved and base_resolved not in target_resolved.parents:
        raise ValueError(f"Path traversal blocked: {target_resolved} is outside {base_resolved}")
    return target_resolved


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file in 64 KiB chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
