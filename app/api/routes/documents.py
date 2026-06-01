from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, BackgroundTasks

from app.core.logging import get_logger
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.services.document_service import DocumentService

logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])


def get_document_service() -> DocumentService:
    from app.main import get_app_state
    return get_app_state().document_service


@router.post("/upload", response_model=DocumentUploadResponse, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_name: str = Form(default=""),
    version: str = Form(default=""),
    effective_date: str = Form(default=""),
    department: str = Form(default=""),
    service: DocumentService = Depends(get_document_service),
) -> DocumentUploadResponse:
    """Upload a policy document for ingestion."""
    file_bytes = await file.read()
    metadata = {
        "document_name": document_name or file.filename,
        "version": version or None,
        "effective_date": effective_date or None,
        "department": department or None,
    }
    document_id = await service.upload(file_bytes, file.filename or "upload", metadata)
    return DocumentUploadResponse(
        document_id=document_id,
        document_name=metadata["document_name"],
        status="processing",
        message="Document accepted for ingestion",
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    """List all ingested documents."""
    return await service.list_documents(limit=limit, offset=offset)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """Get metadata for a specific document."""
    return await service.get_document(document_id)


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    document_id: str,
    service: DocumentService = Depends(get_document_service),
) -> DocumentDeleteResponse:
    """Delete a document and all its indexed chunks."""
    await service.delete_document(document_id)
    return DocumentDeleteResponse(
        document_id=document_id,
        message="Document deleted successfully",
    )
