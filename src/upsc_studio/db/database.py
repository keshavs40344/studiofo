"""SQLite database connection and schema initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    chapter_title TEXT NOT NULL,
    exam_cycle TEXT NOT NULL,
    cutoff_date TEXT NOT NULL,
    target_duration_min INTEGER NOT NULL DEFAULT 30,
    tts_enabled INTEGER NOT NULL DEFAULT 0,
    root_dir TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'NOT_STARTED',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_documents (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    original_path TEXT NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    extraction_status TEXT NOT NULL,
    diagnostics_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS syllabus_items (
    id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    stage TEXT NOT NULL,
    paper TEXT NOT NULL,
    topic TEXT NOT NULL,
    subtopic TEXT NOT NULL,
    keywords_json TEXT NOT NULL,
    source_ref TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS coverage_ledger (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    syllabus_item_id TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    note_refs_json TEXT NOT NULL,
    script_section_id TEXT,
    scene_id TEXT,
    study_ref TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (syllabus_item_id) REFERENCES syllabus_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    publisher TEXT NOT NULL,
    url TEXT,
    pub_date TEXT,
    access_date TEXT NOT NULL,
    source_tier TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    statement TEXT NOT NULL,
    chapter_section TEXT NOT NULL,
    scene_id TEXT,
    source_id TEXT,
    page_or_section TEXT,
    ref_period TEXT,
    status TEXT NOT NULL,
    verification_notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    creator TEXT NOT NULL,
    origin_url TEXT,
    licence TEXT NOT NULL,
    attribution TEXT NOT NULL DEFAULT '',
    rights_status TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS render_jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    status TEXT NOT NULL,
    output_path TEXT,
    input_hash TEXT NOT NULL,
    command TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS qa_gates (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    gate_name TEXT NOT NULL,
    status TEXT NOT NULL,
    blocking_issues_json TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    approved_by TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS backups (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    backup_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys and Row factory enabled."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create tables if missing and record schema version."""
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    conn.commit()
    return conn
