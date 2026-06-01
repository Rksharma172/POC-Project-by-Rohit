from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.logging import get_logger
from app.rag.vectordb import SearchResult

logger = get_logger(__name__)


class BaseReranker(ABC):
    """Abstract re-ranker interface."""

    @abstractmethod
    async def rerank(
        self, query: str, results: list[SearchResult], top_k: int
    ) -> list[SearchResult]:
        ...


class BGEReranker(BaseReranker):
    """Cross-encoder reranker using BAAI/bge-reranker-base."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        device: str = "cpu",
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._model = None

    def _load(self) -> None:
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self._model_name, device=self._device)

    async def rerank(
        self, query: str, results: list[SearchResult], top_k: int
    ) -> list[SearchResult]:
        if not results:
            return results
        self._load()
        try:
            import asyncio
            pairs = [(query, r.text) for r in results]
            loop = asyncio.get_event_loop()
            scores = await loop.run_in_executor(
                None, lambda: self._model.predict(pairs).tolist()
            )
            reranked = sorted(
                zip(results, scores), key=lambda x: x[1], reverse=True
            )
            final = []
            for result, score in reranked[:top_k]:
                result.score = float(score)
                final.append(result)
            logger.debug("reranker_complete", top_k=top_k, total=len(results))
            return final
        except Exception as exc:
            logger.error("reranker_failed_fallback", error=str(exc))
            return results[:top_k]


class PassthroughReranker(BaseReranker):
    """No-op reranker — returns top_k results as-is."""

    async def rerank(
        self, query: str, results: list[SearchResult], top_k: int
    ) -> list[SearchResult]:
        return results[:top_k]


def get_reranker(enabled: bool, model: str = "BAAI/bge-reranker-base") -> BaseReranker:
    if enabled:
        return BGEReranker(model_name=model)
    return PassthroughReranker()
