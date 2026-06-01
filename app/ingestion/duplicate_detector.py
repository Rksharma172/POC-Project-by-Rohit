from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from app.core.logging import get_logger
from app.utils.hash_utils import sha256_of_bytes, sha256_of_text, normalize_text

logger = get_logger(__name__)


class DuplicateType(str, Enum):
    FILE_HASH = "file_hash"
    CONTENT_HASH = "content_hash"
    SEMANTIC = "semantic"


@dataclass
class DuplicateCheckResult:
    is_duplicate: bool
    duplicate_type: DuplicateType | None = None
    existing_document_id: str | None = None
    similarity_score: float | None = None
    message: str = ""


class DocumentHashStore(Protocol):
    """Minimal interface the detector needs — satisfied by DocumentRepository."""

    async def find_by_file_hash(self, file_hash: str) -> str | None:
        ...

    async def find_by_content_hash(self, content_hash: str) -> str | None:
        ...

    async def get_all_document_embeddings(self) -> list[tuple[str, list[float]]]:
        ...


class DuplicateDetector:
    """Three-layer duplicate detection: file hash → content hash → semantic similarity."""

    def __init__(
        self,
        hash_store: DocumentHashStore,
        semantic_threshold: float = 0.95,
        check_file_hash: bool = True,
        check_content_hash: bool = True,
        check_semantic: bool = True,
    ) -> None:
        self._store = hash_store
        self._threshold = semantic_threshold
        self._check_file_hash = check_file_hash
        self._check_content_hash = check_content_hash
        self._check_semantic = check_semantic

    async def check(
        self,
        file_bytes: bytes,
        content_text: str,
        content_embedding: list[float] | None = None,
    ) -> DuplicateCheckResult:
        # ── Layer 1: File hash ─────────────────────────────────────────────────
        if self._check_file_hash:
            file_hash = sha256_of_bytes(file_bytes)
            existing_id = await self._store.find_by_file_hash(file_hash)
            if existing_id:
                logger.warning(
                    "duplicate_detected",
                    type=DuplicateType.FILE_HASH,
                    existing_id=existing_id,
                )
                return DuplicateCheckResult(
                    is_duplicate=True,
                    duplicate_type=DuplicateType.FILE_HASH,
                    existing_document_id=existing_id,
                    message=f"Identical file already ingested (id={existing_id})",
                )

        # ── Layer 2: Normalized content hash ──────────────────────────────────
        if self._check_content_hash:
            normalized = normalize_text(content_text)
            content_hash = sha256_of_text(normalized)
            existing_id = await self._store.find_by_content_hash(content_hash)
            if existing_id:
                logger.warning(
                    "duplicate_detected",
                    type=DuplicateType.CONTENT_HASH,
                    existing_id=existing_id,
                )
                return DuplicateCheckResult(
                    is_duplicate=True,
                    duplicate_type=DuplicateType.CONTENT_HASH,
                    existing_document_id=existing_id,
                    message=f"Document with same normalized content already exists (id={existing_id})",
                )

        # ── Layer 3: Semantic similarity ───────────────────────────────────────
        if self._check_semantic and content_embedding:
            result = await self._check_semantic_similarity(content_embedding)
            if result.is_duplicate:
                return result

        return DuplicateCheckResult(is_duplicate=False)

    async def _check_semantic_similarity(
        self, embedding: list[float]
    ) -> DuplicateCheckResult:
        try:
            stored = await self._store.get_all_document_embeddings()
            if not stored:
                return DuplicateCheckResult(is_duplicate=False)

            import numpy as np

            q = np.array(embedding)
            q_norm = q / (np.linalg.norm(q) + 1e-10)

            for doc_id, stored_emb in stored:
                v = np.array(stored_emb)
                v_norm = v / (np.linalg.norm(v) + 1e-10)
                similarity = float(np.dot(q_norm, v_norm))
                if similarity >= self._threshold:
                    logger.warning(
                        "duplicate_detected",
                        type=DuplicateType.SEMANTIC,
                        existing_id=doc_id,
                        similarity=similarity,
                    )
                    return DuplicateCheckResult(
                        is_duplicate=True,
                        duplicate_type=DuplicateType.SEMANTIC,
                        existing_document_id=doc_id,
                        similarity_score=similarity,
                        message=f"Semantically similar document exists (id={doc_id}, similarity={similarity:.3f})",
                    )
        except Exception as exc:
            logger.error("semantic_duplicate_check_failed", error=str(exc))

        return DuplicateCheckResult(is_duplicate=False)
