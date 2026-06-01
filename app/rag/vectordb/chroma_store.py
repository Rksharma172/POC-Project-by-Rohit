from __future__ import annotations

from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.exceptions import VectorStoreError
from app.core.logging import get_logger
from app.utils.retry import with_retry

from .base import BaseVectorStore, SearchResult

logger = get_logger(__name__)


class ChromaVectorStore(BaseVectorStore):
    """ChromaDB vector store implementation."""

    def __init__(
        self,
        persist_directory: str,
        collection_name: str = "policy_documents",
    ) -> None:
        self._persist_dir = persist_directory
        self._collection_name = collection_name
        self._client: chromadb.PersistentClient | None = None
        self._collection: chromadb.Collection | None = None

    def _get_collection(self) -> chromadb.Collection:
        if self._collection is None:
            self._client = chromadb.PersistentClient(
                path=self._persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    @with_retry(max_attempts=3)
    async def upsert(
        self,
        chunk_id: str,
        embedding: list[float],
        text: str,
        metadata: dict[str, Any],
    ) -> None:
        await self.upsert_batch([chunk_id], [embedding], [text], [metadata])

    @with_retry(max_attempts=3)
    async def upsert_batch(
        self,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        try:
            collection = self._get_collection()
            # ChromaDB metadata values must be str/int/float/bool
            safe_metas = [_sanitize_metadata(m) for m in metadatas]
            collection.upsert(
                ids=chunk_ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=safe_metas,
            )
            logger.debug("chroma_upsert", count=len(chunk_ids))
        except Exception as exc:
            logger.error("chroma_upsert_failed", error=str(exc))
            raise VectorStoreError(f"ChromaDB upsert failed: {exc}") from exc

    @with_retry(max_attempts=3)
    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        try:
            collection = self._get_collection()
            where = _build_where(filters) if filters else None
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            search_results: list[SearchResult] = []
            ids = results.get("ids", [[]])[0]
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]

            for chunk_id, text, meta, dist in zip(ids, docs, metas, dists):
                score = 1.0 - float(dist)  # cosine distance → similarity
                search_results.append(
                    SearchResult(
                        chunk_id=chunk_id,
                        document_id=meta.get("document_id", ""),
                        document_name=meta.get("document_name", ""),
                        text=text,
                        score=score,
                        metadata=meta,
                    )
                )
            return search_results
        except Exception as exc:
            logger.error("chroma_search_failed", error=str(exc))
            raise VectorStoreError(f"ChromaDB search failed: {exc}") from exc

    async def delete_by_document(self, document_id: str) -> int:
        try:
            collection = self._get_collection()
            existing = collection.get(where={"document_id": {"$eq": document_id}})
            ids = existing.get("ids", [])
            if ids:
                collection.delete(ids=ids)
            return len(ids)
        except Exception as exc:
            logger.error("chroma_delete_failed", error=str(exc))
            raise VectorStoreError(f"ChromaDB delete failed: {exc}") from exc

    async def count(self) -> int:
        return self._get_collection().count()


def _sanitize_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Ensure all metadata values are ChromaDB-compatible primitives."""
    safe: dict[str, Any] = {}
    for k, v in meta.items():
        if isinstance(v, (str, int, float, bool)):
            safe[k] = v
        elif v is None:
            safe[k] = ""
        else:
            safe[k] = str(v)
    return safe


def _build_where(filters: dict[str, Any]) -> dict[str, Any]:
    """Convert simple key=value filters to ChromaDB where clause."""
    if len(filters) == 1:
        k, v = next(iter(filters.items()))
        return {k: {"$eq": v}}
    return {"$and": [{k: {"$eq": v}} for k, v in filters.items()]}
