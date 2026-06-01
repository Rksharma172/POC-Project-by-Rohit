from __future__ import annotations

import time
import uuid

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import AskPolicyError
from app.core.logging import get_logger
from app.monitoring.metrics import ERROR_COUNT

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request_id to every request for tracing."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.start_time = time.monotonic()

        import structlog
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        latency = (time.monotonic() - request.state.start_time) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=round(latency),
        )
        return response


async def askpolicy_exception_handler(
    request: Request, exc: AskPolicyError
) -> JSONResponse:
    ERROR_COUNT.labels(error_code=exc.error_code).inc()
    logger.warning(
        "handled_exception",
        error_code=exc.error_code,
        message=exc.message,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "detail": exc.detail,
        },
        headers={"X-Request-ID": getattr(request.state, "request_id", "")},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    ERROR_COUNT.labels(error_code="INTERNAL_ERROR").inc()
    logger.error(
        "unhandled_exception",
        error=str(exc),
        path=request.url.path,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Please try again.",
            "detail": None,
        },
    )
