from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Chunk:
    chunk_id: str
    text: str
    document_id: str
    document_name: str
    chunk_index: int
    section: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.chunk_id:
            self.chunk_id = str(uuid.uuid4())


class TextChunker:
    """Section-aware text chunker with configurable size and overlap.

    Preserves section/heading context in each chunk's metadata.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
        preserve_headings: bool = True,
    ) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._min_chunk_size = min_chunk_size
        self._preserve_headings = preserve_headings

    def chunk(
        self,
        text: str,
        document_id: str,
        document_name: str,
        sections: list[dict[str, Any]] | None = None,
        base_metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        if not text.strip():
            return []

        words = text.split()
        if not words:
            return []

        section_map = self._build_section_map(text, sections or [])
        chunks: list[Chunk] = []
        chunk_index = 0
        start = 0

        while start < len(words):
            end = min(start + self._chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)

            if len(chunk_text.strip()) < self._min_chunk_size and chunks:
                # Merge tiny tail into previous chunk
                prev = chunks[-1]
                prev.text = prev.text + " " + chunk_text
                break

            char_offset = len(" ".join(words[:start]))
            current_section = self._find_section(char_offset, section_map)

            meta = dict(base_metadata or {})
            meta.update(
                {
                    "document_id": document_id,
                    "document_name": document_name,
                    "chunk_index": chunk_index,
                    "section": current_section,
                    "word_count": len(chunk_words),
                }
            )

            if self._preserve_headings and current_section:
                prefixed_text = f"[Section: {current_section}]\n{chunk_text}"
            else:
                prefixed_text = chunk_text

            chunks.append(
                Chunk(
                    chunk_id=f"{document_id}_{chunk_index}",
                    text=prefixed_text,
                    document_id=document_id,
                    document_name=document_name,
                    chunk_index=chunk_index,
                    section=current_section,
                    metadata=meta,
                )
            )

            chunk_index += 1
            # Advance with overlap
            start += self._chunk_size - self._chunk_overlap

        logger.debug(
            "chunking_complete",
            document_id=document_id,
            chunk_count=len(chunks),
            chunk_size=self._chunk_size,
        )
        return chunks

    def _build_section_map(
        self, text: str, sections: list[dict[str, Any]]
    ) -> list[tuple[int, str]]:
        """Build a sorted list of (char_offset, section_name) pairs."""
        section_map: list[tuple[int, str]] = []
        for section in sections:
            heading = section.get("heading", "")
            if not heading:
                continue
            pos = text.find(heading)
            if pos >= 0:
                section_map.append((pos, heading))
        return sorted(section_map, key=lambda x: x[0])

    def _find_section(
        self, char_offset: int, section_map: list[tuple[int, str]]
    ) -> str:
        current = ""
        for offset, name in section_map:
            if offset <= char_offset:
                current = name
            else:
                break
        return current
