"""Optional Docling / PaddleOCR adapter with safe capability detection and fallback."""

from __future__ import annotations

import importlib.util
from pathlib import Path


class DoclingOCRAdapter:
    """Routes complex/scanned PDFs to Docling or PaddleOCR if installed, else reports fallback."""

    @staticmethod
    def capabilities() -> dict:
        return {
            "docling_installed": importlib.util.find_spec("docling") is not None,
            "paddleocr_installed": importlib.util.find_spec("paddleocr") is not None,
            "fallback": "pypdf_text_extraction",
        }

    def extract_if_available(self, pdf_path: Path) -> dict:
        caps = self.capabilities()
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        if not caps["docling_installed"]:
            return {
                "used_adapter": "fallback_required",
                "status": "DOCLING_NOT_INSTALLED",
                "text": "",
                "capabilities": caps,
            }
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        return {
            "used_adapter": "docling",
            "status": "SUCCESS",
            "text": result.document.export_to_markdown(),
            "capabilities": caps,
        }
