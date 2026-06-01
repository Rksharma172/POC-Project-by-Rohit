from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchResult:
    chunk_id: str
    document_id: str
    document_name: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def section(self) -> str | None:
        return self.metadata.get("section")

    @property
    def page(self) -> int | None:
        return self.metadata.get("page")


class BaseVectorStore(ABC):
    """Abstract interface for vector storage backends."""

    @abstractmethod
    async def upsert(
        self,
        chunk_id: str,
        embedding: list[float],
        text: str,
        metadata: dict[str, Any],
    ) -> None:
        """Insert or update a single chunk."""

    @abstractmethod
    async def upsert_batch(
        self,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Batch insert or update chunks."""

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Nearest-neighbour search."""

    @abstractmethod
    async def delete_by_document(self, document_id: str) -> int:
        """Delete all chunks for a document. Returns number of deleted chunks."""

    @abstractmethod
    async def count(self) -> int:
        """Return total number of chunks stored."""

    async def health_check(self) -> bool:
        try:
            await self.count()
            return True
        except Exception:
            return False
