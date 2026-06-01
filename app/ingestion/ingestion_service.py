from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

import aiofiles

from app.core.config import Settings
from app.core.exceptions import (
    DocumentAlreadyExistsError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from app.core.logging import get_logger
from app.ingestion.chunking import TextChunker
from app.ingestion.duplicate_detector import DuplicateDetector
from app.ingestion.parsers.base import get_parser_for_file
from app.models.document import DocumentStatus
from app.rag.embeddings import BaseEmbeddingProvider
from app.rag.vectordb import BaseVectorStore
from app.repositories.document_repository import DocumentRepository
from app.utils.hash_utils import sha256_of_bytes, sha256_of_text, normalize_text

logger = get_logger(__name__)


class DocumentIngestionService:
    """Orchestrates the full document ingestion pipeline.

    Pipeline: Upload → Duplicate Detection → Parse → Chunk → Embed → VectorStore → DB
    """

    def __init__(
        self,
        settings: Settings,
        document_repo: DocumentRepository,
        embedding_provider: BaseEmbeddingProvider,
        vector_store: BaseVectorStore,
    ) -> None:
        self._settings = settings
        self._repo = document_repo
        self._embedder = embedding_provider
        self._vector_store = vector_store
        self._chunker = TextChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        self._detector = DuplicateDetector(
            hash_store=document_repo,
            semantic_threshold=settings.semantic_threshold,
        )

    async def ingest(
        self,
        file_bytes: bytes,
        filename: str,
        metadata: dict | None = None,
    ) -> str:
        """Run the full ingestion pipeline. Returns the document_id."""
        metadata = metadata or {}
        document_id = str(uuid.uuid4())

        # ── Validate ──────────────────────────────────────────────────────────
        await self._validate_file(file_bytes, filename)

        # ── Save upload to disk ───────────────────────────────────────────────
        upload_path = await self._save_upload(file_bytes, filename, document_id)

        # ── Parse ─────────────────────────────────────────────────────────────
        parser = get_parser_for_file(upload_path)
        parsed = await parser.parse(upload_path)
        logger.info("document_parsed", document_id=document_id, word_count=parsed.word_count)

        # ── Duplicate detection ────────────────────────────────────────────────
        file_hash = sha256_of_bytes(file_bytes)
        content_hash = sha256_of_text(normalize_text(parsed.text))

        # Embed first ~2000 chars for semantic dup check
        snippet_embedding = await self._embedder.embed(parsed.text[:2000])

        dup_result = await self._detector.check(
            file_bytes=file_bytes,
            content_text=parsed.text,
            content_embedding=snippet_embedding,
        )
        if dup_result.is_duplicate:
            logger.warning(
                "ingestion_skipped_duplicate",
                document_id=document_id,
                existing_id=dup_result.existing_document_id,
                reason=dup_result.message,
            )
            raise DocumentAlreadyExistsError(
                dup_result.message,
                detail=f"existing_id={dup_result.existing_document_id}",
            )

        # ── Create DB record ──────────────────────────────────────────────────
        await self._repo.create(
            document_id=document_id,
            document_name=metadata.get("document_name", filename),
            original_filename=filename,
            file_type=upload_path.suffix.lstrip(".").lower(),
            file_size_bytes=len(file_bytes),
            file_hash=file_hash,
            content_hash=content_hash,
            version=metadata.get("version"),
            effective_date=metadata.get("effective_date"),
            department=metadata.get("department"),
            status=DocumentStatus.PROCESSING,
        )

        try:
            # ── Chunk ─────────────────────────────────────────────────────────
            chunks = self._chunker.chunk(
                text=parsed.text,
                document_id=document_id,
                document_name=metadata.get("document_name", filename),
                sections=parsed.sections,
                base_metadata={
                    "file_type": upload_path.suffix.lstrip(".").lower(),
                    "version": metadata.get("version", ""),
                    "department": metadata.get("department", ""),
                },
            )

            # ── Embed ─────────────────────────────────────────────────────────
            texts = [c.text for c in chunks]
            embeddings = await self._embedder.embed_batch(texts)

            # ── Store in vector DB ────────────────────────────────────────────
            await self._vector_store.upsert_batch(
                chunk_ids=[c.chunk_id for c in chunks],
                embeddings=embeddings,
                texts=texts,
                metadatas=[c.metadata for c in chunks],
            )

            # ── Update DB status ──────────────────────────────────────────────
            await self._repo.update_status(
                document_id=document_id,
                status=DocumentStatus.READY,
                chunk_count=len(chunks),
                processed_at=datetime.utcnow(),
            )
            logger.info(
                "ingestion_complete",
                document_id=document_id,
                chunks=len(chunks),
            )

        except Exception as exc:
            logger.error("ingestion_failed", document_id=document_id, error=str(exc))
            await self._repo.update_status(
                document_id=document_id,
                status=DocumentStatus.FAILED,
                error_message=str(exc),
            )
            raise

        return document_id

    async def delete(self, document_id: str) -> None:
        """Remove a document from both vector store and DB."""
        deleted_chunks = await self._vector_store.delete_by_document(document_id)
        await self._repo.delete(document_id)
        logger.info("document_deleted", document_id=document_id, chunks_removed=deleted_chunks)

    async def _validate_file(self, file_bytes: bytes, filename: str) -> None:
        path = Path(filename)
        ext = path.suffix.lstrip(".").lower()
        allowed = self._settings.yaml("ingestion", "supported_extensions", default=["pdf", "docx", "txt", "html"])
        if ext not in allowed:
            raise UnsupportedFileTypeError(f"File type '.{ext}' is not supported. Allowed: {allowed}")
        if len(file_bytes) > self._settings.max_upload_bytes:
            raise FileTooLargeError(
                f"File size {len(file_bytes) / 1024 / 1024:.1f} MB exceeds limit of {self._settings.max_file_size_mb} MB"
            )

    async def _save_upload(self, file_bytes: bytes, filename: str, document_id: str) -> Path:
        upload_dir = Path(self._settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(filename).suffix
        dest = upload_dir / f"{document_id}{suffix}"
        async with aiofiles.open(dest, "wb") as f:
            await f.write(file_bytes)
        return dest
