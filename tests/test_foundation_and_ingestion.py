"""Tests for Phase 0-2: hardware audit, project lifecycle, backup/restore, and document ingestion."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest

from upsc_studio.core.hardware import detect_hardware
from upsc_studio.core.paths import ensure_within_base
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, VerificationStatus
from upsc_studio.ingestion.ingestor import DocumentIngestor
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.research.verifier import EvidenceEngine


def test_hardware_detection_returns_real_values(tmp_path: Path) -> None:
    hw = detect_hardware(tmp_path)
    assert hw.physical_cores >= 1
    assert hw.total_ram_gb > 0
    assert hw.free_disk_gb > 0
    assert hw.ffmpeg_path is not None


def test_path_traversal_blocked(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ensure_within_base(tmp_path, tmp_path / ".." / "escape.txt")


def test_project_create_reopen_backup_and_restore(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "studio.db")
    mgr = ProjectManager(conn, tmp_path / "projects")
    proj = mgr.create_project(
        ProjectCreate(name="Monetary Policy", chapter_title="RBI Monetary Policy Committee")
    )
    reopened = mgr.get_project(proj.id)
    assert reopened.chapter_title == "RBI Monetary Policy Committee"

    marker = Path(proj.root_dir) / "teaching" / "custom_note.txt"
    marker.write_text("preserve me", encoding="utf-8")

    evidence = EvidenceEngine(conn, Path(proj.root_dir))
    source_id = evidence.add_source(
        proj.id,
        title="Official Constitution",
        publisher="Ministry of Law and Justice",
        source_tier="PRIMARY_OFFICIAL",
        url="https://legislative.gov.in/",
        pub_date="2024-05-01",
    )
    claim_id = evidence.add_claim(
        proj.id,
        "Part III contains Fundamental Rights.",
        "Constitutional Basis",
        status=VerificationStatus.HUMAN_REVIEW_REQUIRED,
        source_id=source_id,
        page_or_section="Part III",
    )

    bkp_zip = mgr.backup_project(proj.id, tmp_path / "backups", notes="pre-migration")
    assert bkp_zip.exists()

    marker.unlink()
    conn.execute("DELETE FROM claims WHERE id = ?", (claim_id,))
    conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    conn.commit()
    assert not marker.exists()
    assert conn.execute("SELECT 1 FROM claims WHERE id = ?", (claim_id,)).fetchone() is None
    assert conn.execute("SELECT 1 FROM sources WHERE id = ?", (source_id,)).fetchone() is None

    restored = mgr.restore_project(bkp_zip)
    assert restored.id == proj.id
    assert marker.read_text(encoding="utf-8") == "preserve me"
    assert conn.execute("SELECT 1 FROM claims WHERE id = ?", (claim_id,)).fetchone() is not None
    assert conn.execute("SELECT 1 FROM sources WHERE id = ?", (source_id,)).fetchone() is not None

    # A fresh database must also receive the project evidence, not just its files.
    fresh_conn = init_db(tmp_path / "restored.db")
    fresh_mgr = ProjectManager(fresh_conn, tmp_path / "restored_projects")
    fresh_project = fresh_mgr.restore_project(bkp_zip)
    assert fresh_project.id == proj.id
    assert (Path(fresh_project.root_dir) / "teaching" / "custom_note.txt").read_text(encoding="utf-8") == "preserve me"
    assert fresh_conn.execute("SELECT 1 FROM claims WHERE id = ?", (claim_id,)).fetchone() is not None
    assert fresh_conn.execute("SELECT 1 FROM sources WHERE id = ?", (source_id,)).fetchone() is not None


def test_document_ingestion_formats_and_duplicates(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "studio.db")
    mgr = ProjectManager(conn, tmp_path / "projects")
    proj = mgr.create_project(ProjectCreate(name="Ingestion Test", chapter_title="Tenth Schedule"))
    ingestor = DocumentIngestor(conn, Path(proj.root_dir))

    md_file = tmp_path / "notes.md"
    md_file.write_text("# Anti-Defection Law\n\nAdded by 52nd Amendment Act 1985.", encoding="utf-8")
    r1 = ingestor.ingest_file(proj.id, md_file)
    assert r1.extraction_status == "SUCCESS"
    assert r1.is_duplicate is False
    assert Path(r1.original_path).exists()

    # Duplicate detection by SHA-256
    r2 = ingestor.ingest_file(proj.id, md_file)
    assert r2.is_duplicate is True

    # DOCX ingestion
    import docx

    docx_path = tmp_path / "notes.docx"
    d = docx.Document()
    d.add_paragraph("Article 102(2) deals with disqualification on ground of defection.")
    d.save(docx_path)
    r3 = ingestor.ingest_file(proj.id, docx_path)
    assert r3.extraction_status == "SUCCESS"
    assert "Article 102(2)" in r3.pages[0].text

    # Image without tesseract -> honest OCR_UNAVAILABLE
    from PIL import Image

    img_path = tmp_path / "handwritten.png"
    Image.new("RGB", (200, 100), color=(255, 255, 255)).save(img_path)
    r4 = ingestor.ingest_file(proj.id, img_path)
    assert r4.extraction_status in {"OCR_UNAVAILABLE", "EMPTY", "SUCCESS"}
