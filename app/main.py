from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.middleware.exception_handler import (
    RequestContextMiddleware,
    askpolicy_exception_handler,
    generic_exception_handler,
)
from app.api.routes import chat, documents, health
from app.cache.redis_cache import RedisCache
from app.core.config import get_settings
from app.core.exceptions import AskPolicyError
from app.core.logging import configure_logging, get_logger
from app.ingestion.ingestion_service import DocumentIngestionService
from app.rag.embeddings import EmbeddingFactory
from app.rag.llm import LLMFactory
from app.rag.pipeline import RAGPipeline
from app.rag.reranker import get_reranker
from app.rag.vectordb import VectorDBFactory
from app.repositories.document_repository import DocumentRepository
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService

logger = get_logger(__name__)


@dataclass
class AppState:
    """Holds all singleton application dependencies."""

    document_repo: DocumentRepository = field(default=None)
    embedding_provider: Any = field(default=None)
    vector_store: Any = field(default=None)
    llm_provider: Any = field(default=None)
    cache: RedisCache | None = field(default=None)
    document_service: DocumentService = field(default=None)
    chat_service: ChatService = field(default=None)


_app_state: AppState | None = None


def get_app_state() -> AppState:
    if _app_state is None:
        raise RuntimeError("Application not initialised")
    return _app_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _app_state

    settings = get_settings()
    configure_logging(
        level=settings.yaml("logging", "level", default="INFO"),
        fmt=settings.yaml("logging", "format", default="json"),
    )
    logger.info("startup", app=settings.app_name, env=settings.app_env)

    # ── Build dependencies ─────────────────────────────────────────────────────
    embedding_provider = EmbeddingFactory.create(settings)
    vector_store = VectorDBFactory.create(settings)
    llm_provider = LLMFactory.create(settings)
    reranker = get_reranker(
        enabled=bool(settings.yaml("search", "reranking_enabled", default=False)),
        model=settings.yaml("search", "reranker_model", default="BAAI/bge-reranker-base"),
    )

    cache: RedisCache | None = None
    if settings.cache_enabled:
        cache = RedisCache(url=settings.redis_url, default_ttl=settings.cache_ttl)

    document_repo = DocumentRepository(database_url=settings.database_url)
    await document_repo.init_db()

    ingestion_service = DocumentIngestionService(
        settings=settings,
        document_repo=document_repo,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    rag_pipeline = RAGPipeline(
        settings=settings,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        llm_provider=llm_provider,
        reranker=reranker,
    )

    _app_state = AppState(
        document_repo=document_repo,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        llm_provider=llm_provider,
        cache=cache,
        document_service=DocumentService(
            repo=document_repo,
            ingestion_service=ingestion_service,
        ),
        chat_service=ChatService(
            pipeline=rag_pipeline,
            cache=cache,
            settings=settings,
        ),
    )

    logger.info("startup_complete", provider=settings.llm_provider, model=settings.llm_model)
    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    if cache:
        await cache.close()
    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AskPolicy — Internal Policy Q&A",
        description="Enterprise RAG system for HR policies, SOPs, and compliance documents.",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Middleware ─────────────────────────────────────────────────────────────
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],          # tighten for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ─────────────────────────────────────────────────────
    app.add_exception_handler(AskPolicyError, askpolicy_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # ── Routes ─────────────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")

    # ── Prometheus metrics ─────────────────────────────────────────────────────
    if settings.yaml("monitoring", "prometheus_enabled", default=True):
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    return app


app = create_app()
