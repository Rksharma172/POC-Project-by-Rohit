from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

# ── Celery app ─────────────────────────────────────────────────────────────────
# Instantiated lazily to avoid import-time side effects when Celery isn't needed.

_celery_app = None


def get_celery_app():
    global _celery_app
    if _celery_app is None:
        from celery import Celery
        from app.core.config import get_settings

        settings = get_settings()
        _celery_app = Celery(
            "askpolicy",
            broker=settings.celery_broker_url,
            backend=settings.celery_result_backend,
        )
        _celery_app.conf.update(
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            timezone="UTC",
            enable_utc=True,
            task_track_started=True,
            worker_prefetch_multiplier=1,
        )
    return _celery_app


# ── Async ingestion task ───────────────────────────────────────────────────────

def ingest_document_async(
    document_id: str,
    file_path: str,
    filename: str,
    metadata: dict,
) -> str:
    """Submit an ingestion job to Celery. Returns task_id."""
    app = get_celery_app()
    task = app.send_task(
        "askpolicy.ingest_document",
        args=[document_id, file_path, filename, metadata],
    )
    logger.info(f"ingestion_task_submitted task_id={task.id} document_id={document_id}")
    return task.id


# ── Background task (FastAPI fallback when Celery not available) ───────────────

async def ingest_document_background(
    document_id: str,
    file_bytes: bytes,
    filename: str,
    metadata: dict,
    ingestion_service,
) -> None:
    """FastAPI BackgroundTask wrapper for ingestion."""
    try:
        await ingestion_service.ingest(file_bytes, filename, metadata)
    except Exception as exc:
        logger.error(f"background_ingestion_failed document_id={document_id} error={exc}")
