from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.core.exceptions import DocumentParseError
from app.core.logging import get_logger

from .base import BaseParser, ParsedDocument

logger = get_logger(__name__)


class HTMLParser(BaseParser):
    """HTML document parser using BeautifulSoup4."""

    def supported_extensions(self) -> list[str]:
        return ["html", "htm"]

    async def parse(self, file_path: Path) -> ParsedDocument:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._parse_sync, file_path)

    def _parse_sync(self, file_path: Path) -> ParsedDocument:
        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise DocumentParseError("beautifulsoup4 not installed. Run: pip install beautifulsoup4") from exc

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            soup = BeautifulSoup(content, "lxml")

            # Remove script and style elements
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()

            sections: list[dict[str, Any]] = []
            for heading_tag in soup.find_all(["h1", "h2", "h3", "h4"]):
                text = heading_tag.get_text(strip=True)
                if text:
                    sections.append({"heading": text, "tag": heading_tag.name})

            full_text = soup.get_text(separator="\n", strip=True)
            return ParsedDocument(
                text=full_text,
                sections=sections,
                metadata={
                    "file_type": "html",
                    "file_name": file_path.name,
                    "title": soup.title.string if soup.title else "",
                },
            )
        except Exception as exc:
            logger.error("html_parse_failed", file=str(file_path), error=str(exc))
            raise DocumentParseError(f"Failed to parse HTML '{file_path.name}': {exc}") from exc
