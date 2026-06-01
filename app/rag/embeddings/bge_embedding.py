from __future__ import annotations

from app.core.exceptions import EmbeddingError
from app.core.logging import get_logger

from .base import BaseEmbeddingProvider

logger = get_logger(__name__)


class BGEEmbeddingProvider(BaseEmbeddingProvider):
    """BGE local embedding provider using sentence-transformers."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-base-en-v1.5",
        device: str = "cpu",
        dims: int = 768,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._dims = dims
        self._model = None  # lazy-loaded

    def _load_model(self) -> None:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name, device=self._device)
            except Exception as exc:
                raise EmbeddingError(f"Failed to load BGE model: {exc}") from exc

    def provider_name(self) -> str:
        return "bge"

    def dimensions(self) -> int:
        return self._dims

    async def embed(self, text: str) -> list[float]:
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._load_model()
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: self._model.encode(
                    texts,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                ).tolist(),
            )
            return embeddings
        except Exception as exc:
            logger.error("bge_embedding_failed", error=str(exc))
            raise EmbeddingError(f"BGE embedding failed: {exc}") from exc
