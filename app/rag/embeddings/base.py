from __future__ import annotations

from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    """Abstract base for all embedding providers.

    Embeddings are always generated here — never through the LLM provider.
    """

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Embed a single text string."""

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text strings."""

    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding vector dimension."""

    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""

    async def health_check(self) -> bool:
        try:
            result = await self.embed("health check")
            return len(result) == self.dimensions()
        except Exception:
            return False
