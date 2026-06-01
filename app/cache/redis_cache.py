from __future__ import annotations

import hashlib
import json
from typing import Any

import redis.asyncio as aioredis

from app.core.logging import get_logger

logger = get_logger(__name__)


class RedisCache:
    """Redis cache with support for embeddings, retrievals, and full responses.

    Cache key strategy: SHA256(question + corpus_fingerprint)
    Invalidation: update corpus_fingerprint when documents change.
    """

    def __init__(self, url: str, default_ttl: int = 3600) -> None:
        self._url = url
        self._default_ttl = default_ttl
        self._client: aioredis.Redis | None = None

    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                self._url, encoding="utf-8", decode_responses=True
            )
        return self._client

    # ── Public API ─────────────────────────────────────────────────────────────

    async def get(self, key: str) -> Any | None:
        try:
            client = await self._get_client()
            raw = await client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning("cache_get_failed", key=key[:50], error=str(exc))
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        try:
            client = await self._get_client()
            serialized = json.dumps(value)
            await client.setex(key, ttl or self._default_ttl, serialized)
        except Exception as exc:
            logger.warning("cache_set_failed", key=key[:50], error=str(exc))

    async def delete(self, key: str) -> None:
        try:
            client = await self._get_client()
            await client.delete(key)
        except Exception as exc:
            logger.warning("cache_delete_failed", key=key[:50], error=str(exc))

    async def delete_pattern(self, pattern: str) -> int:
        try:
            client = await self._get_client()
            keys = await client.keys(pattern)
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as exc:
            logger.warning("cache_delete_pattern_failed", pattern=pattern, error=str(exc))
            return 0

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            return await client.ping()
        except Exception:
            return False

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Key builders ───────────────────────────────────────────────────────────

    @staticmethod
    def response_key(question: str, corpus_fingerprint: str) -> str:
        raw = f"response:{question}:{corpus_fingerprint}"
        return "ask:" + hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def embedding_key(text: str) -> str:
        raw = f"emb:{text}"
        return "ask:emb:" + hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def retrieval_key(question: str, top_k: int, filters_hash: str) -> str:
        raw = f"retrieval:{question}:{top_k}:{filters_hash}"
        return "ask:ret:" + hashlib.sha256(raw.encode()).hexdigest()

    # ── Corpus fingerprint management ──────────────────────────────────────────

    async def get_corpus_fingerprint(self) -> str:
        client = await self._get_client()
        fp = await client.get("ask:corpus:fingerprint")
        return fp or "initial"

    async def set_corpus_fingerprint(self, fingerprint: str) -> None:
        client = await self._get_client()
        await client.set("ask:corpus:fingerprint", fingerprint)

    async def invalidate_response_cache(self) -> int:
        """Call when documents change — clears all response + retrieval caches."""
        deleted = await self.delete_pattern("ask:ret:*")
        deleted += await self.delete_pattern("ask:[a-f0-9]*")
        logger.info("cache_invalidated", keys_deleted=deleted)
        return deleted
