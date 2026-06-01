from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.rag.embeddings import BaseEmbeddingProvider
from app.rag.vectordb import BaseVectorStore, SearchResult

logger = get_logger(__name__)


@dataclass
class HybridSearchConfig:
    top_k: int = 5
    semantic_weight: float = 0.7
    bm25_weight: float = 0.3
    use_bm25: bool = True


class HybridSearchService:
    """Combines semantic vector search with BM25 keyword search.

    Scores are merged using Reciprocal Rank Fusion (RRF).
    """

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider,
        vector_store: BaseVectorStore,
        config: HybridSearchConfig | None = None,
    ) -> None:
        self._embedder = embedding_provider
        self._vector_store = vector_store
        self._config = config or HybridSearchConfig()

    async def search(
        self,
        question: str,
        top_k: int | None = None,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        k = top_k or self._config.top_k
        fetch_k = k * 3  # fetch more then merge

        # ── Semantic search ────────────────────────────────────────────────────
        query_embedding = await self._embedder.embed(question)
        semantic_results = await self._vector_store.search(
            query_embedding=query_embedding,
            top_k=fetch_k,
            filters=filters,
        )

        if not self._config.use_bm25 or not semantic_results:
            return semantic_results[:k]

        # ── BM25 keyword search on the retrieved candidate pool ────────────────
        try:
            bm25_results = self._bm25_rerank(
                query=question,
                candidates=semantic_results,
            )
        except Exception as exc:
            logger.warning("bm25_failed_fallback_semantic", error=str(exc))
            return semantic_results[:k]

        # ── Merge via Reciprocal Rank Fusion ───────────────────────────────────
        merged = self._rrf_merge(
            semantic_results,
            bm25_results,
            semantic_weight=self._config.semantic_weight,
            bm25_weight=self._config.bm25_weight,
        )

        logger.debug(
            "hybrid_search_complete",
            question_snippet=question[:60],
            returned=len(merged[:k]),
        )
        return merged[:k]

    def _bm25_rerank(
        self, query: str, candidates: list[SearchResult]
    ) -> list[SearchResult]:
        from rank_bm25 import BM25Okapi

        tokenized_corpus = [doc.text.lower().split() for doc in candidates]
        bm25 = BM25Okapi(tokenized_corpus)
        scores = bm25.get_scores(query.lower().split())

        scored = sorted(
            zip(candidates, scores), key=lambda x: x[1], reverse=True
        )
        results = []
        for doc, score in scored:
            doc.metadata["bm25_score"] = float(score)
            results.append(doc)
        return results

    def _rrf_merge(
        self,
        semantic: list[SearchResult],
        bm25: list[SearchResult],
        semantic_weight: float,
        bm25_weight: float,
        k: int = 60,
    ) -> list[SearchResult]:
        rrf_scores: dict[str, float] = {}
        chunk_map: dict[str, SearchResult] = {}

        for rank, result in enumerate(semantic):
            rrf_scores[result.chunk_id] = rrf_scores.get(result.chunk_id, 0.0) + (
                semantic_weight / (k + rank + 1)
            )
            chunk_map[result.chunk_id] = result

        for rank, result in enumerate(bm25):
            rrf_scores[result.chunk_id] = rrf_scores.get(result.chunk_id, 0.0) + (
                bm25_weight / (k + rank + 1)
            )
            chunk_map[result.chunk_id] = result

        merged = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        ordered: list[SearchResult] = []
        for chunk_id, rrf_score in merged:
            result = chunk_map[chunk_id]
            result.score = rrf_score
            ordered.append(result)
        return ordered
