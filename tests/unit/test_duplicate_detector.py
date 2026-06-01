from __future__ import annotations

import pytest

from app.utils.hash_utils import sha256_of_bytes, sha256_of_text, normalize_text, corpus_fingerprint


def test_sha256_bytes_consistency() -> None:
    data = b"hello world"
    assert sha256_of_bytes(data) == sha256_of_bytes(data)


def test_sha256_text_consistency() -> None:
    text = "policy document content"
    assert sha256_of_text(text) == sha256_of_text(text)


def test_normalize_text_collapses_whitespace() -> None:
    text1 = "hello   world\t\there"
    text2 = "hello world here"
    assert normalize_text(text1) == normalize_text(text2)


def test_normalize_text_is_case_insensitive() -> None:
    assert normalize_text("HELLO World") == normalize_text("hello world")


def test_corpus_fingerprint_order_independent() -> None:
    hashes = ["abc123", "def456", "ghi789"]
    fp1 = corpus_fingerprint(hashes)
    fp2 = corpus_fingerprint(list(reversed(hashes)))
    assert fp1 == fp2


def test_corpus_fingerprint_changes_with_new_doc() -> None:
    hashes = ["abc123", "def456"]
    fp1 = corpus_fingerprint(hashes)
    fp2 = corpus_fingerprint(hashes + ["new999"])
    assert fp1 != fp2


@pytest.mark.asyncio
async def test_duplicate_detector_file_hash() -> None:
    from unittest.mock import AsyncMock
    from app.ingestion.duplicate_detector import DuplicateDetector

    mock_store = AsyncMock()
    mock_store.find_by_file_hash.return_value = "existing-doc-id"
    mock_store.find_by_content_hash.return_value = None
    mock_store.get_all_document_embeddings.return_value = []

    detector = DuplicateDetector(hash_store=mock_store, semantic_threshold=0.95)
    result = await detector.check(b"test file bytes", "some content")

    assert result.is_duplicate is True
    assert result.existing_document_id == "existing-doc-id"
    assert result.duplicate_type.value == "file_hash"


@pytest.mark.asyncio
async def test_duplicate_detector_no_duplicate() -> None:
    from unittest.mock import AsyncMock
    from app.ingestion.duplicate_detector import DuplicateDetector

    mock_store = AsyncMock()
    mock_store.find_by_file_hash.return_value = None
    mock_store.find_by_content_hash.return_value = None
    mock_store.get_all_document_embeddings.return_value = []

    detector = DuplicateDetector(hash_store=mock_store)
    result = await detector.check(b"unique bytes", "unique content")

    assert result.is_duplicate is False
