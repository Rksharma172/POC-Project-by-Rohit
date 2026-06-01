from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.logging import get_logger
from app.monitoring.metrics import record_rag_query
from app.schemas.chat import ChatQueryRequest, ChatQueryResponse
from app.services.chat_service import ChatService

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])


def get_chat_service() -> ChatService:
    from app.main import get_app_state
    return get_app_state().chat_service


@router.post("/query", response_model=ChatQueryResponse)
async def query(
    request: Request,
    body: ChatQueryRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatQueryResponse:
    """Ask a question about internal policies."""
    # user_id would come from auth middleware in production
    user_id = request.headers.get("X-User-ID")

    response = await service.query(body, user_id=user_id)

    record_rag_query(
        latency_ms=response.latency_ms or 0,
        confidence=response.confidence,
        token_usage=response.token_usage or {},
        cache_hit=response.cache_hit,
    )

    return response
