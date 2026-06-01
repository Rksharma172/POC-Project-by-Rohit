from __future__ import annotations

import pytest

from app.rag.guardrails import AnswerValidator, NOT_FOUND_RESPONSE
from app.rag.vectordb.base import SearchResult


def _make_result(text: str, score: float = 0.8) -> SearchResult:
    return SearchResult(
        chunk_id="c1",
        document_id="d1",
        document_name="HR Policy",
        text=text,
        score=score,
    )


def test_empty_answer_fails() -> None:
    validator = AnswerValidator(min_confidence=0.5)
    result = validator.validate("", [], [])
    assert not result.is_valid
    assert result.safe_response == NOT_FOUND_RESPONSE


def test_not_found_literal_is_valid() -> None:
    validator = AnswerValidator(min_confidence=0.5)
    result = validator.validate(NOT_FOUND_RESPONSE, [], [])
    assert result.is_valid


def test_well_grounded_answer_passes() -> None:
    chunk_text = (
        "employees are entitled to twenty days annual leave per year "
        "according to the leave policy handbook"
    )
    answer = (
        "Employees are entitled to twenty days annual leave per year "
        "according to the leave policy handbook section three."
    )
    chunks = [_make_result(chunk_text, score=0.9)]
    citations = [{"document": "HR Policy", "section": "Leave Policy"}]

    validator = AnswerValidator(min_confidence=0.3)
    result = validator.validate(answer, chunks, citations)
    assert result.is_valid
    assert result.confidence > 0.3


def test_low_confidence_returns_safe_response() -> None:
    chunks = [_make_result("completely unrelated content about widgets", score=0.1)]
    answer = "The sky is blue and cats are nice animals in the forest."
    validator = AnswerValidator(min_confidence=0.7)
    result = validator.validate(answer, chunks, [])
    assert not result.is_valid
    assert result.safe_response is not None
