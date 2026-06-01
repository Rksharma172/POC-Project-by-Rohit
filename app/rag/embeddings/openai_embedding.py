from __future__ import annotations

from openai import AsyncOpenAI

from app.core.exceptions import EmbeddingError
from app.core.logging import get_logger
from app.utils.retry import with_retry

from .base import BaseEmbeddingProvider

logger = get_logger(__name__)


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI text embedding provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dims: int = 1536,
        batch_size: int = 100,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._dims = dims
        self._batch_size = batch_size

    def provider_name(self) -> str:
        return "openai"

    def dimensions(self) -> int:
        return self._dims

    @with_retry(max_attempts=3)
    async def embed(self, text: str) -> list[float]:
        result = await self.embed_batch([text])
        return result[0]

    @with_retry(max_attempts=3)
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            all_embeddings: list[list[float]] = []
            for i in range(0, len(texts), self._batch_size):
                batch = texts[i : i + self._batch_size]
                response = await self._client.embeddings.create(
                    input=batch,
                    model=self._model,
                    dimensions=self._dims,
                )
                all_embeddings.extend([item.embedding for item in response.data])
            return all_embeddings
        except Exception as exc:
            logger.error("openai_embedding_failed", error=str(exc))
            raise EmbeddingError(f"OpenAI embedding failed: {exc}") from exc
