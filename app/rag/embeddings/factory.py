from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import ProviderNotSupportedError
from app.core.logging import get_logger

from .base import BaseEmbeddingProvider

logger = get_logger(__name__)


class EmbeddingFactory:
    """Creates the configured embedding provider.

    Add a new provider: implement BaseEmbeddingProvider, register here.
    Switching from OpenAI to BGE requires only a config.yaml change.
    """

    @staticmethod
    def create(settings: Settings) -> BaseEmbeddingProvider:
        provider = settings.embedding_provider.lower()
        logger.info(
            "creating_embedding_provider",
            provider=provider,
            model=settings.embedding_model,
        )

        if provider == "openai":
            from .openai_embedding import OpenAIEmbeddingProvider
            api_key = settings.openai_embedding_api_key or settings.openai_api_key
            return OpenAIEmbeddingProvider(
                api_key=api_key,
                model=settings.embedding_model,
                dims=settings.embedding_dimensions,
                batch_size=int(settings.yaml("embeddings", "batch_size", default=100)),
            )

        if provider == "bge":
            from .bge_embedding import BGEEmbeddingProvider
            return BGEEmbeddingProvider(
                model_name=settings.embedding_model,
                device=settings.yaml("embeddings", "device", default="cpu"),
                dims=settings.embedding_dimensions,
            )

        if provider == "e5":
            # E5 models use the same SentenceTransformer interface as BGE
            from .bge_embedding import BGEEmbeddingProvider
            return BGEEmbeddingProvider(
                model_name=settings.embedding_model,
                device=settings.yaml("embeddings", "device", default="cpu"),
                dims=settings.embedding_dimensions,
            )

        raise ProviderNotSupportedError(
            f"Embedding provider '{provider}' is not supported. "
            f"Supported: openai, bge, e5"
        )
