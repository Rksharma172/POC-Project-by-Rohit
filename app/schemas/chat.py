from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ChatQueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000, description="The policy question to answer")
    session_id: Optional[str] = Field(default=None, description="Optional session ID for context")
    top_k: Optional[int] = Field(default=None, ge=1, le=20, description="Override default top-K retrieval")
    filters: Optional[dict] = Field(default=None, description="Metadata filters (e.g., department, version)")


class Citation(BaseModel):
    document: str
    document_id: str
    section: Optional[str] = None
    page: Optional[int] = None
    chunk_text: Optional[str] = Field(default=None, description="Relevant excerpt")
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ChatQueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    session_id: Optional[str] = None
    cache_hit: bool = False
    latency_ms: Optional[float] = None
    token_usage: Optional[dict] = None


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: Optional[str] = None
