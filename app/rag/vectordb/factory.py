from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import ProviderNotSupportedError
from app.core.logging import get_logger

from .base import BaseVectorStore

logger = get_logger(__name__)


class VectorDBFactory:
    """Creates the configured vector store backend.

    Switching from ChromaDB to Pinecone/FAISS requires only config.yaml change.
    """

    @staticmethod
    def create(settings: Settings) -> BaseVectorStore:
        provider = settings.vectordb_provider.lower()
        logger.info("creating_vectordb_provider", provider=provider)

        if provider == "chromadb":
            from .chroma_store import ChromaVectorStore
            return ChromaVectorStore(
                persist_directory=settings.chroma_persist_dir,
                collection_name=settings.vectordb_collection,
            )

        if provider == "pinecone":
            raise ProviderNotSupportedError(
                "Pinecone provider stub — implement PineconeVectorStore and register here."
            )

        if provider == "weaviate":
            raise ProviderNotSupportedError(
                "Weaviate provider stub — implement WeaviateVectorStore and register here."
            )

        if provider == "faiss":
            raise ProviderNotSupportedError(
                "FAISS provider stub — implement FAISSVectorStore and register here."
            )

        raise ProviderNotSupportedError(
            f"VectorDB provider '{provider}' is not supported. "
            f"Supported: chromadb, pinecone, weaviate, faiss"
        )
