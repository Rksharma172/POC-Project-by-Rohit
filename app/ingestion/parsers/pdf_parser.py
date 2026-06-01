from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.core.exceptions import DocumentParseError
from app.core.logging import get_logger

from .base import BaseParser, ParsedDocument

logger = get_logger(__name__)


class PDFParser(BaseParser):
    """PDF document parser using PyMuPDF (fitz)."""

    def supported_extensions(self) -> list[str]:
        return ["pdf"]

    async def parse(self, file_path: Path) -> ParsedDocument:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._parse_sync, file_path)

    def _parse_sync(self, file_path: Path) -> ParsedDocument:
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise DocumentParseError("PyMuPDF not installed. Run: pip install pymupdf") from exc

        try:
            doc = fitz.open(str(file_path))
            pages: list[str] = []
            sections: list[dict[str, Any]] = []
            full_text_parts: list[str] = []
            current_section = ""

            for page_num, page in enumerate(doc, start=1):
                page_text = page.get_text("text")
                pages.append(page_text)
                full_text_parts.append(page_text)

                # Extract headings from block structure
                blocks = page.get_text("dict").get("blocks", [])
                for block in blocks:
                    if block.get("type") == 0:  # text block
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                if span.get("size", 0) > 14 and span.get("text", "").strip():
                                    heading = span["text"].strip()
                                    current_section = heading
                                    sections.append(
                                        {"heading": heading, "page": page_num}
                                    )

            doc.close()
            full_text = "\n".join(full_text_parts)
            return ParsedDocument(
                text=full_text,
                pages=pages,
                sections=sections,
                metadata={
                    "page_count": len(pages),
                    "file_type": "pdf",
                    "file_name": file_path.name,
                },
            )
        except Exception as exc:
            logger.error("pdf_parse_failed", file=str(file_path), error=str(exc))
            raise DocumentParseError(f"Failed to parse PDF '{file_path.name}': {exc}") from exc
