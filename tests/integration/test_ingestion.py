from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from app.core.config import Settings
from app.ingestion.ingestion_service import DocumentIngestionService


@pytest.fixture
def mock_settings(tmp_path) -> Settings:
    settings = MagicMock(spec=Settings)
    settings.chunk_size = 200
    settings.chunk_overlap = 20
    settings.semantic_threshold = 0.95
    settings.max_upload_bytes = 10 * 1024 * 1024
    settings.max_file_size_mb = 10
    settings.upload_dir = str(tmp_path / "uploads")
    settings.yaml.return_value = ["pdf", "docx", "txt", "html"]
    return settings


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_file_hash.return_value = None
    repo.find_by_content_hash.return_value = None
    repo.get_all_document_embeddings.return_value = []
    repo.create.return_value = MagicMock(id="test-doc-id")
    return repo


@pytest.fixture
def mock_embedder() -> AsyncMock:
    embedder = AsyncMock()
    embedder.embed.return_value = [0.1] * 1536
    embedder.embed_batch.return_value = [[0.1] * 1536] * 5
    return embedder


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_ingest_txt_document(
    mock_settings, mock_repo, mock_embedder, mock_vector_store, tmp_path
) -> None:
    service = DocumentIngestionService(
        settings=mock_settings,
        document_repo=mock_repo,
        embedding_provider=mock_embedder,
        vector_store=mock_vector_store,
    )

    content = "This is a test policy document.\n" * 50
    file_bytes = content.encode("utf-8")

    doc_id = await service.ingest(
        file_bytes=file_bytes,
        filename="test_policy.txt",
        metadata={"document_name": "Test Policy", "department": "HR"},
    )

    assert doc_id is not None
    mock_repo.create.assert_called_once()
    mock_embedder.embed_batch.assert_called()
    mock_vector_store.upsert_batch.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_duplicate_raises(
    mock_settings, mock_embedder, mock_vector_store
) -> None:
    from app.core.exceptions import DocumentAlreadyExistsError

    repo = AsyncMock()
    repo.find_by_file_hash.return_value = "existing-doc-id"
    repo.find_by_content_hash.return_value = None
    repo.get_all_document_embeddings.return_value = []

    service = DocumentIngestionService(
        settings=mock_settings,
        document_repo=repo,
        embedding_provider=mock_embedder,
        vector_store=mock_vector_store,
    )

    with pytest.raises(DocumentAlreadyExistsError):
        await service.ingest(b"duplicate content", "duplicate.txt", {})
