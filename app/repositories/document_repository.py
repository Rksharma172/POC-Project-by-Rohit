from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.logging import get_logger
from app.models.document import Base, Document, DocumentStatus
from app.repositories.base import BaseRepository

logger = get_logger(__name__)


class DocumentRepository(BaseRepository[Document]):
    """SQLAlchemy-backed document metadata repository."""

    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False
        )

    async def init_db(self) -> None:
        """Create tables if they don't exist."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_initialized")

    # ── BaseRepository interface ───────────────────────────────────────────────

    async def get_by_id(self, id: str) -> Document | None:
        async with self._session_factory() as session:
            result = await session.execute(select(Document).where(Document.id == id))
            return result.scalar_one_or_none()

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Document]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Document)
                .order_by(Document.upload_time.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())

    async def delete(self, id: str) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(delete(Document).where(Document.id == id))
            await session.commit()
            return result.rowcount > 0

    async def count(self) -> int:
        async with self._session_factory() as session:
            result = await session.execute(select(func.count()).select_from(Document))
            return result.scalar_one()

    # ── Additional methods ─────────────────────────────────────────────────────

    async def create(
        self,
        document_id: str,
        document_name: str,
        original_filename: str,
        file_type: str,
        file_size_bytes: int,
        file_hash: str,
        content_hash: str | None = None,
        version: str | None = None,
        effective_date: str | None = None,
        department: str | None = None,
        status: DocumentStatus = DocumentStatus.PENDING,
    ) -> Document:
        doc = Document(
            id=document_id,
            document_name=document_name,
            original_filename=original_filename,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            file_hash=file_hash,
            content_hash=content_hash,
            version=version,
            effective_date=effective_date,
            department=department,
            status=status,
        )
        async with self._session_factory() as session:
            session.add(doc)
            await session.commit()
            await session.refresh(doc)
        return doc

    async def update_status(
        self,
        document_id: str,
        status: DocumentStatus,
        chunk_count: int | None = None,
        processed_at: datetime | None = None,
        error_message: str | None = None,
    ) -> None:
        values: dict[str, Any] = {"status": status}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        if processed_at is not None:
            values["processed_at"] = processed_at
        if error_message is not None:
            values["error_message"] = error_message
        async with self._session_factory() as session:
            await session.execute(
                update(Document).where(Document.id == document_id).values(**values)
            )
            await session.commit()

    # ── Duplicate detection support ────────────────────────────────────────────

    async def find_by_file_hash(self, file_hash: str) -> str | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Document.id)
                .where(Document.file_hash == file_hash)
                .where(Document.status != DocumentStatus.FAILED)
            )
            row = result.scalar_one_or_none()
            return str(row) if row else None

    async def find_by_content_hash(self, content_hash: str) -> str | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Document.id)
                .where(Document.content_hash == content_hash)
                .where(Document.status != DocumentStatus.FAILED)
            )
            row = result.scalar_one_or_none()
            return str(row) if row else None

    async def get_all_file_hashes(self) -> list[str]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Document.file_hash).where(Document.status == DocumentStatus.READY)
            )
            return [row[0] for row in result.all()]

    async def get_all_document_embeddings(self) -> list[tuple[str, list[float]]]:
        """Placeholder: in production store document-level embeddings separately."""
        return []
