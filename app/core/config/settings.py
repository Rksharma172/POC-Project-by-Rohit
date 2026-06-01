from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config.yaml"


def _load_yaml() -> dict[str, Any]:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────────
    app_name: str = "AskPolicy"
    app_version: str = "0.1.0"
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="APP_DEBUG")
    secret_key: str = Field(default="change-me", alias="SECRET_KEY")

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── LLM ───────────────────────────────────────────────────────────────────
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    azure_openai_api_key: str = Field(default="", alias="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: str = Field(default="", alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_version: str = Field(
        default="2024-02-15-preview", alias="AZURE_OPENAI_API_VERSION"
    )
    azure_openai_deployment: str = Field(default="", alias="AZURE_OPENAI_DEPLOYMENT")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    ollama_base_url: str = Field(
        default="http://localhost:11434", alias="OLLAMA_BASE_URL"
    )

    # ── Embeddings ────────────────────────────────────────────────────────────
    openai_embedding_api_key: str = Field(default="", alias="OPENAI_EMBEDDING_API_KEY")

    # ── Vector DB ─────────────────────────────────────────────────────────────
    pinecone_api_key: str = Field(default="", alias="PINECONE_API_KEY")
    pinecone_index: str = Field(default="policy-docs", alias="PINECONE_INDEX")
    weaviate_url: str = Field(default="http://localhost:8080", alias="WEAVIATE_URL")
    weaviate_api_key: str = Field(default="", alias="WEAVIATE_API_KEY")

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/askpolicy.db", alias="DATABASE_URL"
    )

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # ── Celery ────────────────────────────────────────────────────────────────
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1", alias="CELERY_BROKER_URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2", alias="CELERY_RESULT_BACKEND"
    )

    # ── File Upload ───────────────────────────────────────────────────────────
    upload_dir: str = Field(default="./data/uploads", alias="UPLOAD_DIR")
    max_file_size_mb: int = Field(default=50, alias="MAX_FILE_SIZE_MB")

    model_config = {"env_file": ".env", "populate_by_name": True, "extra": "ignore"}

    # ── YAML overlay ─────────────────────────────────────────────────────────
    _yaml: dict[str, Any] = {}

    def model_post_init(self, __context: Any) -> None:
        self._yaml = _load_yaml()

    def yaml(self, *keys: str, default: Any = None) -> Any:
        """Drill into nested YAML config: yaml('llm', 'model')."""
        node = self._yaml
        for k in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(k, default)
        return node

    # ── Convenience properties ────────────────────────────────────────────────
    @property
    def llm_provider(self) -> str:
        return self.yaml("llm", "provider", default="openai")

    @property
    def llm_model(self) -> str:
        return self.yaml("llm", "model", default="gpt-4o-mini")

    @property
    def llm_temperature(self) -> float:
        return float(self.yaml("llm", "temperature", default=0.1))

    @property
    def llm_max_tokens(self) -> int:
        return int(self.yaml("llm", "max_tokens", default=2000))

    @property
    def embedding_provider(self) -> str:
        return self.yaml("embeddings", "provider", default="openai")

    @property
    def embedding_model(self) -> str:
        return self.yaml("embeddings", "model", default="text-embedding-3-small")

    @property
    def embedding_dimensions(self) -> int:
        return int(self.yaml("embeddings", "dimensions", default=1536))

    @property
    def vectordb_provider(self) -> str:
        return self.yaml("vectordb", "provider", default="chromadb")

    @property
    def vectordb_collection(self) -> str:
        return self.yaml("vectordb", "collection_name", default="policy_documents")

    @property
    def chroma_persist_dir(self) -> str:
        return self.yaml("vectordb", "persist_directory", default="./data/chroma")

    @property
    def chunk_size(self) -> int:
        return int(self.yaml("chunking", "chunk_size", default=512))

    @property
    def chunk_overlap(self) -> int:
        return int(self.yaml("chunking", "chunk_overlap", default=50))

    @property
    def search_top_k(self) -> int:
        return int(self.yaml("search", "top_k", default=5))

    @property
    def semantic_threshold(self) -> float:
        return float(
            self.yaml("duplicate_detection", "semantic_threshold", default=0.95)
        )

    @property
    def cache_enabled(self) -> bool:
        return bool(self.yaml("cache", "enabled", default=True))

    @property
    def cache_ttl(self) -> int:
        return int(self.yaml("cache", "ttl_seconds", default=3600))

    @property
    def guardrails_enabled(self) -> bool:
        return bool(self.yaml("guardrails", "enabled", default=True))

    @property
    def min_confidence(self) -> float:
        return float(self.yaml("guardrails", "min_confidence", default=0.5))

    @property
    def max_upload_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
