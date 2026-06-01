from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["Health"])


@router.get("/health")
async def health() -> JSONResponse:
    """Basic liveness probe."""
    return JSONResponse({"status": "ok", "service": "AskPolicy"})


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    """Readiness probe — checks all dependencies."""
    from app.main import get_app_state

    state = get_app_state()
    checks: dict[str, str] = {}
    overall = "ok"

    # Vector store
    try:
        vs_ok = await state.vector_store.health_check()
        checks["vector_store"] = "ok" if vs_ok else "degraded"
    except Exception as exc:
        checks["vector_store"] = f"error: {exc}"
        overall = "degraded"

    # Embeddings
    try:
        emb_ok = await state.embedding_provider.health_check()
        checks["embeddings"] = "ok" if emb_ok else "degraded"
    except Exception as exc:
        checks["embeddings"] = f"error: {exc}"
        overall = "degraded"

    # Cache
    try:
        cache_ok = await state.cache.health_check() if state.cache else True
        checks["cache"] = "ok" if cache_ok else "degraded"
    except Exception as exc:
        checks["cache"] = f"error: {exc}"

    status_code = 200 if overall == "ok" else 503
    return JSONResponse(
        {"status": overall, "checks": checks},
        status_code=status_code,
    )
