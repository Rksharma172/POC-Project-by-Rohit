from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.rag.pipeline import RAGPipeline, RAGResult
from app.rag.vectordb.base import SearchResult
from app.rag.guardrails import NOT_FOUND_RESPONSE


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.search_top_k = 5
    settings.min_confidence = 0.3
    settings.yaml.return_value = True
    return settings


@pytest.fixture
def mock_embedding_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.embed.return_value = [0.1] * 1536
    return provider


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    store = AsyncMock()
    store.search.return_value = [
        SearchResult(
            chunk_id="c1",
            document_id="d1",
            document_name="HR Leave Policy",
            text=(
                "Employees are entitled to 20 days of annual leave per year. "
                "Leave requests must be submitted at least two weeks in advance. "
                "Unused leave can be carried over for up to 90 days."
            ),
            score=0.92,
            metadata={"section": "Annual Leave", "department": "HR"},
        )
    ]
    return store


@pytest.fixture
def mock_llm() -> AsyncMock:
    from app.rag.llm.base import LLMResponse
    llm = AsyncMock()
    llm.complete.return_value = LLMResponse(
        content=(
            "Employees are entitled to 20 days of annual leave per year.\n\n"
            "SOURCE: HR Leave Policy | Section: Annual Leave | Relevance: high"
        ),
        model="gpt-4o-mini",
        usage={"prompt_tokens": 150, "completion_tokens": 50, "total_tokens": 200},
    )
    return llm


@pytest.fixture
def mock_reranker() -> AsyncMock:
    from app.rag.reranker import BaseReranker
    reranker = AsyncMock(spec=BaseReranker)
    reranker.rerank.side_effect = lambda q, results, top_k: results[:top_k]
    return reranker


@pytest.mark.asyncio
async def test_rag_pipeline_returns_answer(
    mock_settings,
    mock_embedding_provider,
    mock_vector_store,
    mock_llm,
    mock_reranker,
) -> None:
    pipeline = RAGPipeline(
        settings=mock_settings,
        embedding_provider=mock_embedding_provider,
        vector_store=mock_vector_store,
        llm_provider=mock_llm,
        reranker=mock_reranker,
    )

    result = await pipeline.query("How many days of annual leave do I get?")

    assert isinstance(result, RAGResult)
    assert "20 days" in result.answer
    assert len(result.citations) > 0
    assert result.confidence > 0


@pytest.mark.asyncio
async def test_rag_pipeline_no_chunks_returns_not_found(
    mock_settings,
    mock_embedding_provider,
    mock_vector_store,
    mock_llm,
    mock_reranker,
) -> None:
    mock_vector_store.search.return_value = []

    pipeline = RAGPipeline(
        settings=mock_settings,
        embedding_provider=mock_embedding_provider,
        vector_store=mock_vector_store,
        llm_provider=mock_llm,
        reranker=mock_reranker,
    )

    result = await pipeline.query("What is the expense claim limit for alien planets?")
    assert result.answer == NOT_FOUND_RESPONSE
