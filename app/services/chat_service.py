from __future__ import annotations

import json
import uuid

from app.cache.redis_cache import RedisCache
from app.core.config import Settings
from app.core.logging import get_logger
from app.rag.pipeline import RAGPipeline, RAGResult
from app.schemas.chat import ChatQueryRequest, ChatQueryResponse, Citation

logger = get_logger(__name__)


class ChatService:
    """Handles the Q&A request lifecycle including caching."""

    def __init__(
        self,
        pipeline: RAGPipeline,
        cache: RedisCache | None,
        settings: Settings,
    ) -> None:
        self._pipeline = pipeline
        self._cache = cache
        self._settings = settings

    async def query(
        self, request: ChatQueryRequest, user_id: str | None = None
    ) -> ChatQueryResponse:
        session_id = request.session_id or str(uuid.uuid4())

        # ── Cache lookup ───────────────────────────────────────────────────────
        corpus_fp = "v1"  # TODO: fetch from DocumentService
        cache_key = None
        if self._cache and self._settings.cache_enabled:
            cache_key = RedisCache.response_key(request.question, corpus_fp)
            cached = await self._cache.get(cache_key)
            if cached:
                logger.info("cache_hit", session_id=session_id)
                return ChatQueryResponse(**cached, cache_hit=True, session_id=session_id)

        # ── RAG pipeline ───────────────────────────────────────────────────────
        result: RAGResult = await self._pipeline.query(
            question=request.question,
            top_k=request.top_k,
            filters=request.filters,
        )

        response = ChatQueryResponse(
            answer=result.answer,
            citations=result.citations,
            confidence=result.confidence,
            session_id=session_id,
            cache_hit=False,
            latency_ms=result.latency_ms,
            token_usage=result.token_usage,
        )

        # ── Cache store ────────────────────────────────────────────────────────
        if self._cache and cache_key and self._settings.cache_enabled:
            await self._cache.set(
                cache_key,
                response.model_dump(),
                ttl=self._settings.yaml("cache", "response_cache_ttl", default=86400),
            )

        logger.info(
            "chat_query",
            user_id=user_id,
            session_id=session_id,
            question=request.question[:80],
            confidence=result.confidence,
            latency_ms=result.latency_ms,
            tokens=result.token_usage.get("total_tokens", 0),
        )
        return response
