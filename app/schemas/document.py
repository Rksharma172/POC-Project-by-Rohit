from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    document_id: str
    document_name: str
    status: str
    message: str


class DocumentMetadata(BaseModel):
    version: Optional[str] = None
    effective_date: Optional[str] = None
    department: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class DocumentResponse(BaseModel):
    id: str
    document_name: str
    original_filename: str
    file_type: str
    file_size_bytes: int
    version: Optional[str]
    effective_date: Optional[str]
    department: Optional[str]
    status: str
    chunk_count: int
    upload_time: datetime
    processed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    total: int
    items: list[DocumentResponse]


class DocumentDeleteResponse(BaseModel):
    document_id: str
    message: str
