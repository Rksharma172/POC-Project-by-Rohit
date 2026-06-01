from __future__ import annotations

from app.core.exceptions import DocumentNotFoundError
from app.core.logging import get_logger
from app.ingestion.ingestion_service import DocumentIngestionService
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.utils.hash_utils import corpus_fingerprint

logger = get_logger(__name__)


class DocumentService:
    """Application-level document management service."""

    def __init__(
        self,
        repo: DocumentRepository,
        ingestion_service: DocumentIngestionService,
    ) -> None:
        self._repo = repo
        self._ingestion = ingestion_service

    async def upload(
        self,
        file_bytes: bytes,
        filename: str,
        metadata: dict | None = None,
    ) -> str:
        """Upload and ingest a document. Returns document_id."""
        return await self._ingestion.ingest(file_bytes, filename, metadata)

    async def list_documents(
        self, limit: int = 50, offset: int = 0
    ) -> DocumentListResponse:
        docs = await self._repo.list_all(limit=limit, offset=offset)
        total = await self._repo.count()
        return DocumentListResponse(
            total=total,
            items=[DocumentResponse.model_validate(d) for d in docs],
        )

    async def get_document(self, document_id: str) -> DocumentResponse:
        doc = await self._repo.get_by_id(document_id)
        if not doc:
            raise DocumentNotFoundError(f"Document '{document_id}' not found")
        return DocumentResponse.model_validate(doc)

    async def delete_document(self, document_id: str) -> None:
        doc = await self._repo.get_by_id(document_id)
        if not doc:
            raise DocumentNotFoundError(f"Document '{document_id}' not found")
        await self._ingestion.delete(document_id)

    async def get_corpus_fingerprint(self) -> str:
        hashes = await self._repo.get_all_file_hashes()
        return corpus_fingerprint(hashes) if hashes else "empty"
