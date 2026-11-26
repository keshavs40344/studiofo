"""Multi-format document ingestion with provenance, hashing, and diagnostics."""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from upsc_studio.core.paths import sha256_file
from upsc_studio.db.schemas import utc_now_iso


@dataclass
class PageContent:
    page_number: int
    text: str
    warnings: list[str]


@dataclass
class IngestionResult:
    doc_id: str
    filename: str
    file_type: str
    sha256: str
    original_path: str
    page_count: int
    extraction_status: str
    is_duplicate: bool
    pages: list[PageContent]
    headings: list[str]
    warnings: list[str]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["pages"] = [asdict(p) for p in self.pages]
        return data


class DocumentIngestor:
    """Ingests user notes without modifying originals and tracks extraction quality."""

    def __init__(self, conn: sqlite3.Connection, project_dir: Path) -> None:
        self.conn = conn
        self.project_dir = project_dir
        self.originals_dir = project_dir / "inputs" / "originals"
        self.extracted_dir = project_dir / "inputs" / "extracted"
        self.originals_dir.mkdir(parents=True, exist_ok=True)
        self.extracted_dir.mkdir(parents=True, exist_ok=True)

    def ingest_file(self, project_id: str, source_path: Path) -> IngestionResult:
        """Copy original file into project, extract text/pages, and persist metadata."""
        if not source_path.exists() or not source_path.is_file():
            raise FileNotFoundError(f"Input file not found: {source_path}")

        file_hash = sha256_file(source_path)
        dup_row = self.conn.execute(
            "SELECT id, filename FROM source_documents WHERE project_id = ? AND sha256 = ?",
            (project_id, file_hash),
        ).fetchone()
        is_duplicate = dup_row is not None

        doc_id = f"doc_{uuid.uuid4().hex[:10]}"
        ext = source_path.suffix.lower()
        dest_original = self.originals_dir / f"{doc_id}_{source_path.name}"
        shutil.copy2(source_path, dest_original)

        pages, warnings, status = self._extract_by_extension(dest_original, ext)
        if is_duplicate:
            warnings.append(f"Duplicate content of existing document {dup_row['id']} ({dup_row['filename']}).")

        headings = self._extract_headings(pages)
        result = IngestionResult(
            doc_id=doc_id,
            filename=source_path.name,
            file_type=ext.lstrip(".") or "unknown",
            sha256=file_hash,
            original_path=str(dest_original),
            page_count=len(pages),
            extraction_status=status,
            is_duplicate=is_duplicate,
            pages=pages,
            headings=headings,
            warnings=warnings,
        )

        self._persist(project_id, result)
        return result

    def ingest_text(self, project_id: str, title: str, text: str) -> IngestionResult:
        """Ingest user-typed notes as a preserved Markdown file."""
        safe_name = f"{title.strip().replace(' ', '_')[:40] or 'typed_notes'}.md"
        temp_path = self.originals_dir / f"tmp_{uuid.uuid4().hex[:6]}_{safe_name}"
        temp_path.write_text(text, encoding="utf-8")
        try:
            return self.ingest_file(project_id, temp_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _extract_by_extension(self, path: Path, ext: str) -> tuple[list[PageContent], list[str], str]:
        warnings: list[str] = []
        pages: list[PageContent] = []
        try:
            if ext in {".txt", ".md"}:
                content = path.read_text(encoding="utf-8", errors="replace")
                pages = [PageContent(page_number=1, text=content, warnings=[])]
                status = "SUCCESS" if content.strip() else "EMPTY"
            elif ext == ".pdf":
                pages, warnings, status = self._extract_pdf(path)
            elif ext == ".docx":
                pages, warnings, status = self._extract_docx(path)
            elif ext == ".pptx":
                pages, warnings, status = self._extract_pptx(path)
            elif ext == ".xlsx":
                pages, warnings, status = self._extract_xlsx(path)
            elif ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}:
                pages, warnings, status = self._extract_image_ocr(path)
            else:
                warnings.append(f"Unsupported file extension: {ext}")
                status = "FAILED"
        except Exception as exc:
            warnings.append(f"Extraction error: {exc}")
            status = "FAILED"
        return pages, warnings, status

    @staticmethod
    def _extract_pdf(path: Path) -> tuple[list[PageContent], list[str], str]:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages: list[PageContent] = []
        warnings: list[str] = []
        empty_pages = 0
        for idx, page in enumerate(reader.pages, start=1):
            txt = (page.extract_text() or "").strip()
            p_warn: list[str] = []
            if not txt:
                empty_pages += 1
                p_warn.append("No extractable text (possibly scanned image or diagram).")
            pages.append(PageContent(page_number=idx, text=txt, warnings=p_warn))

        if empty_pages == len(pages) and len(pages) > 0:
            warnings.append("All PDF pages lack selectable text; OCR required (Tesseract not run).")
            return pages, warnings, "NEEDS_OCR"
        if empty_pages > 0:
            warnings.append(f"{empty_pages}/{len(pages)} PDF pages had no selectable text.")
            return pages, warnings, "PARTIAL"
        return pages, warnings, "SUCCESS"

    @staticmethod
    def _extract_docx(path: Path) -> tuple[list[PageContent], list[str], str]:
        import docx

        doc = docx.Document(str(path))
        blocks = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_txt = " | ".join(cell.text.strip() for cell in row.cells)
                if row_txt.strip(" |"):
                    blocks.append(row_txt)
        text = "\n".join(blocks)
        return [PageContent(page_number=1, text=text, warnings=[])], [], "SUCCESS" if text else "EMPTY"

    @staticmethod
    def _extract_pptx(path: Path) -> tuple[list[PageContent], list[str], str]:
        from pptx import Presentation

        prs = Presentation(str(path))
        pages: list[PageContent] = []
        for idx, slide in enumerate(prs.slides, start=1):
            parts = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    parts.append(shape.text.strip())
            pages.append(PageContent(page_number=idx, text="\n".join(parts), warnings=[]))
        return pages, [], "SUCCESS" if any(p.text for p in pages) else "EMPTY"

    @staticmethod
    def _extract_xlsx(path: Path) -> tuple[list[PageContent], list[str], str]:
        import openpyxl

        wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
        pages: list[PageContent] = []
        for idx, sheet in enumerate(wb.worksheets, start=1):
            lines = [f"## Sheet: {sheet.title}"]
            for row in sheet.iter_rows(values_only=True):
                vals = ["" if v is None else str(v) for v in row]
                if any(vals):
                    lines.append(" | ".join(vals))
            pages.append(PageContent(page_number=idx, text="\n".join(lines), warnings=[]))
        wb.close()
        return pages, [], "SUCCESS" if any(p.text for p in pages) else "EMPTY"

    @staticmethod
    def _extract_image_ocr(path: Path) -> tuple[list[PageContent], list[str], str]:
        tesseract = shutil.which("tesseract")
        if not tesseract:
            msg = "OCR unavailable: tesseract is not installed. Image preserved without text extraction."
            return [PageContent(page_number=1, text="", warnings=[msg])], [msg], "OCR_UNAVAILABLE"
        out = subprocess.check_output(
            [tesseract, str(path), "stdout", "--oem", "3", "--psm", "6"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=30,
        ).strip()
        return [PageContent(page_number=1, text=out, warnings=[])], [], "SUCCESS" if out else "EMPTY"

    @staticmethod
    def _extract_headings(pages: list[PageContent]) -> list[str]:
        headings: list[str] = []
        for p in pages:
            for line in p.text.splitlines():
                s = line.strip()
                if s.startswith("#") or (len(s) <= 80 and s.isupper() and len(s) >= 4):
                    headings.append(s.lstrip("# ").strip())
        return headings[:50]

    def _persist(self, project_id: str, result: IngestionResult) -> None:
        out_json = self.extracted_dir / f"{result.doc_id}.json"
        out_json.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        diagnostics = {
            "is_duplicate": result.is_duplicate,
            "headings": result.headings,
            "warnings": result.warnings,
            "extracted_json": str(out_json),
        }
        self.conn.execute(
            """
            INSERT INTO source_documents (
                id, project_id, filename, file_type, sha256, original_path,
                page_count, extraction_status, diagnostics_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.doc_id,
                project_id,
                result.filename,
                result.file_type,
                result.sha256,
                result.original_path,
                result.page_count,
                result.extraction_status,
                json.dumps(diagnostics, ensure_ascii=False),
                utc_now_iso(),
            ),
        )
        self.conn.commit()
        self._write_report(project_id)

    def _write_report(self, project_id: str) -> None:
        rows = self.conn.execute(
            "SELECT * FROM source_documents WHERE project_id = ? ORDER BY created_at",
            (project_id,),
        ).fetchall()
        report = [
            {
                "doc_id": r["id"],
                "filename": r["filename"],
                "file_type": r["file_type"],
                "sha256": r["sha256"],
                "page_count": r["page_count"],
                "extraction_status": r["extraction_status"],
                "diagnostics": json.loads(r["diagnostics_json"]),
            }
            for r in rows
        ]
        (self.extracted_dir / "ingestion_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
