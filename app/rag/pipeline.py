from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.prompts.templates import build_prompts
from app.rag.embeddings import BaseEmbeddingProvider
from app.rag.guardrails import AnswerValidator, NOT_FOUND_RESPONSE
from app.rag.llm import BaseLLMProvider
from app.rag.reranker import BaseReranker
from app.rag.search import HybridSearchService, HybridSearchConfig
from app.rag.vectordb import BaseVectorStore, SearchResult
from app.schemas.chat import Citation

logger = get_logger(__name__)


@dataclass
class RAGResult:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    confidence: float = 0.0
    cache_hit: bool = False
    latency_ms: float = 0.0
    token_usage: dict[str, int] = field(default_factory=dict)
    retrieved_chunks: list[SearchResult] = field(default_factory=list)


class RAGPipeline:
    """Full RAG pipeline: Question → Embed → Search → Rerank → Prompt → LLM → Guardrails.

    All providers are injected — switch any component via config without touching this class.
    """

    def __init__(
        self,
        settings: Settings,
        embedding_provider: BaseEmbeddingProvider,
        vector_store: BaseVectorStore,
        llm_provider: BaseLLMProvider,
        reranker: BaseReranker,
    ) -> None:
        self._settings = settings
        self._search = HybridSearchService(
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            config=HybridSearchConfig(
                top_k=settings.search_top_k,
                use_bm25=bool(settings.yaml("search", "hybrid_search", default=True)),
                semantic_weight=float(settings.yaml("search", "semantic_weight", default=0.7)),
                bm25_weight=float(settings.yaml("search", "bm25_weight", default=0.3)),
            ),
        )
        self._llm = llm_provider
        self._reranker = reranker
        self._validator = AnswerValidator(
            min_confidence=settings.min_confidence,
            require_citations=bool(settings.yaml("guardrails", "require_citations", default=True)),
        )

    async def query(
        self,
        question: str,
        top_k: int | None = None,
        filters: dict | None = None,
    ) -> RAGResult:
        start = time.monotonic()

        # ── 1. Retrieve ───────────────────────────────────────────────────────
        chunks = await self._search.search(question, top_k=top_k, filters=filters)
        if not chunks:
            logger.info("rag_no_chunks_found", question=question[:80])
            return RAGResult(answer=NOT_FOUND_RESPONSE, confidence=1.0)

        # ── 2. Re-rank ────────────────────────────────────────────────────────
        top_k_final = top_k or self._settings.search_top_k
        chunks = await self._reranker.rerank(question, chunks, top_k=top_k_final)

        # ── 3. Build prompt ───────────────────────────────────────────────────
        chunk_dicts = [
            {
                "text": c.text,
                "document_name": c.document_name,
                "document_id": c.document_id,
                "section": c.section or "",
                "score": c.score,
            }
            for c in chunks
        ]
        system_prompt, user_prompt = build_prompts(question, chunk_dicts)

        # ── 4. LLM completion ─────────────────────────────────────────────────
        llm_response = await self._llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # ── 5. Parse citations ─────────────────────────────────────────────────
        answer_text, citations = self._parse_response(llm_response.content, chunks)

        # ── 6. Guardrails ─────────────────────────────────────────────────────
        validation = self._validator.validate(
            answer=answer_text,
            retrieved_chunks=chunks,
            citations=[c.model_dump() for c in citations],
        )

        final_answer = validation.safe_response if not validation.is_valid else answer_text
        confidence = validation.confidence

        latency_ms = (time.monotonic() - start) * 1000
        logger.info(
            "rag_query_complete",
            question=question[:80],
            chunks_used=len(chunks),
            confidence=confidence,
            latency_ms=round(latency_ms),
            total_tokens=llm_response.total_tokens,
        )

        return RAGResult(
            answer=final_answer or NOT_FOUND_RESPONSE,
            citations=citations,
            confidence=confidence,
            latency_ms=round(latency_ms, 2),
            token_usage=llm_response.usage,
            retrieved_chunks=chunks,
        )

    def _parse_response(
        self, raw: str, chunks: list[SearchResult]
    ) -> tuple[str, list[Citation]]:
        """Split LLM output into answer body and structured citations."""
        citations: list[Citation] = []

        # Match "SOURCE: Doc Name | Section: Section Name | Relevance: high"
        source_pattern = re.compile(
            r"SOURCE:\s*(.+?)\s*\|\s*Section:\s*(.+?)\s*\|\s*Relevance:\s*(\w+)",
            re.IGNORECASE,
        )
        matches = source_pattern.findall(raw)

        cited_chunk_map: dict[str, SearchResult] = {
            c.document_name.lower(): c for c in chunks
        }

        for doc_name, section, relevance in matches:
            doc_name = doc_name.strip()
            chunk = cited_chunk_map.get(doc_name.lower())
            citations.append(
                Citation(
                    document=doc_name,
                    document_id=chunk.document_id if chunk else "",
                    section=section.strip(),
                    relevance_score=_relevance_to_score(relevance),
                    chunk_text=chunk.text[:200] if chunk else None,
                )
            )

        # Strip the SOURCE lines from the answer
        answer = source_pattern.sub("", raw).strip()

        # If no explicit citations in response, auto-generate from top chunks
        if not citations and chunks:
            for chunk in chunks[:3]:
                citations.append(
                    Citation(
                        document=chunk.document_name,
                        document_id=chunk.document_id,
                        section=chunk.section or "",
                        relevance_score=round(float(chunk.score), 3),
                    )
                )

        return answer, citations


def _relevance_to_score(relevance: str) -> float:
    mapping = {"high": 0.9, "medium": 0.6, "low": 0.3}
    return mapping.get(relevance.lower().strip(), 0.5)
