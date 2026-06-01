from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedDocument:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    pages: list[str] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)
    word_count: int = 0

    def __post_init__(self) -> None:
        if not self.word_count:
            self.word_count = len(self.text.split())


class BaseParser(ABC):
    """Abstract document parser."""

    @abstractmethod
    async def parse(self, file_path: Path) -> ParsedDocument:
        """Parse a file and return structured text + metadata."""

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return the file extensions this parser handles."""

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lstrip(".").lower() in self.supported_extensions()


def get_parser_for_file(file_path: Path) -> BaseParser:
    """Return the appropriate parser for a given file."""
    from app.ingestion.parsers.pdf_parser import PDFParser
    from app.ingestion.parsers.docx_parser import DOCXParser
    from app.ingestion.parsers.html_parser import HTMLParser
    from app.ingestion.parsers.txt_parser import TXTParser

    ext = file_path.suffix.lstrip(".").lower()
    parsers: list[BaseParser] = [PDFParser(), DOCXParser(), HTMLParser(), TXTParser()]
    for parser in parsers:
        if ext in parser.supported_extensions():
            return parser
    from app.core.exceptions import UnsupportedFileTypeError
    raise UnsupportedFileTypeError(f"No parser available for file type: .{ext}")
