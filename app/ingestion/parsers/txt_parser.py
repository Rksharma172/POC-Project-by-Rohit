from __future__ import annotations

import asyncio
from pathlib import Path

import aiofiles

from app.core.exceptions import DocumentParseError
from app.core.logging import get_logger

from .base import BaseParser, ParsedDocument

logger = get_logger(__name__)


class TXTParser(BaseParser):
    """Plain text document parser."""

    def supported_extensions(self) -> list[str]:
        return ["txt", "md", "rst"]

    async def parse(self, file_path: Path) -> ParsedDocument:
        try:
            async with aiofiles.open(file_path, encoding="utf-8", errors="replace") as f:
                content = await f.read()

            sections = []
            for line in content.splitlines():
                stripped = line.strip()
                # Treat lines starting with # as headings (Markdown-style)
                if stripped.startswith("#"):
                    sections.append({"heading": stripped.lstrip("#").strip()})
                # Treat ALL-CAPS short lines as potential section headers
                elif stripped.isupper() and 3 < len(stripped) < 80:
                    sections.append({"heading": stripped})

            return ParsedDocument(
                text=content,
                sections=sections,
                metadata={
                    "file_type": "txt",
                    "file_name": file_path.name,
                    "line_count": content.count("\n"),
                },
            )
        except Exception as exc:
            logger.error("txt_parse_failed", file=str(file_path), error=str(exc))
            raise DocumentParseError(f"Failed to parse text file '{file_path.name}': {exc}") from exc
