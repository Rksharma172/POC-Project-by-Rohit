from __future__ import annotations

import pytest

from app.ingestion.chunking.chunker import TextChunker, Chunk


@pytest.fixture
def chunker() -> TextChunker:
    return TextChunker(chunk_size=100, chunk_overlap=10, min_chunk_size=20)


def test_chunk_basic(chunker: TextChunker) -> None:
    text = " ".join(f"word{i}" for i in range(250))
    chunks = chunker.chunk(text, "doc1", "Test Document")
    assert len(chunks) > 1
    for chunk in chunks:
        assert isinstance(chunk, Chunk)
        assert chunk.document_id == "doc1"


def test_chunk_ids_are_unique(chunker: TextChunker) -> None:
    text = " ".join(f"word{i}" for i in range(300))
    chunks = chunker.chunk(text, "doc1", "Test Document")
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))


def test_chunk_empty_text(chunker: TextChunker) -> None:
    chunks = chunker.chunk("", "doc1", "Test Document")
    assert chunks == []


def test_chunk_preserves_section(chunker: TextChunker) -> None:
    text = "Introduction This is an introduction section. " * 20
    sections = [{"heading": "Introduction"}]
    chunks = chunker.chunk(text, "doc1", "Test Doc", sections=sections)
    assert any("Introduction" in c.text for c in chunks)


def test_chunk_overlap(chunker: TextChunker) -> None:
    text = " ".join(str(i) for i in range(500))
    chunks = chunker.chunk(text, "doc1", "Test Doc")
    # With overlap, adjacent chunks should share some words
    if len(chunks) >= 2:
        words0 = set(chunks[0].text.split())
        words1 = set(chunks[1].text.split())
        assert len(words0 & words1) > 0
