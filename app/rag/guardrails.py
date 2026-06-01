from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.logging import get_logger
from app.rag.vectordb import SearchResult

logger = get_logger(__name__)

NOT_FOUND_RESPONSE = "Information not found in current policy documents."
LOW_CONFIDENCE_RESPONSE = (
    "I was unable to find a reliable answer in the current policy documents. "
    "Please consult your HR department or the relevant policy owner directly."
)


@dataclass
class ValidationResult:
    is_valid: bool
    confidence: float
    safe_response: str | None = None
    reason: str = ""


class AnswerValidator:
    """Anti-hallucination guardrail layer.

    Validates that the LLM answer is grounded in the retrieved chunks.
    """

    def __init__(
        self,
        min_confidence: float = 0.5,
        require_citations: bool = True,
    ) -> None:
        self._min_confidence = min_confidence
        self._require_citations = require_citations

    def validate(
        self,
        answer: str,
        retrieved_chunks: list[SearchResult],
        citations: list[dict],
    ) -> ValidationResult:
        if not answer or not answer.strip():
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                safe_response=NOT_FOUND_RESPONSE,
                reason="Empty answer from LLM",
            )

        # ── Check for "not found" answer ───────────────────────────────────────
        if NOT_FOUND_RESPONSE.lower() in answer.lower():
            return ValidationResult(
                is_valid=True,
                confidence=1.0,
                reason="LLM correctly reported information not found",
            )

        # ── Grounding check: answer tokens overlap with retrieved chunks ────────
        grounding_score = self._compute_grounding_score(answer, retrieved_chunks)

        # ── Citations check ────────────────────────────────────────────────────
        has_citations = bool(citations)

        # ── Compute overall confidence ─────────────────────────────────────────
        retrieval_score = max((r.score for r in retrieved_chunks), default=0.0)
        confidence = self._compute_confidence(
            grounding_score=grounding_score,
            retrieval_score=float(retrieval_score),
            has_citations=has_citations,
        )

        if confidence < self._min_confidence:
            logger.warning(
                "guardrail_low_confidence",
                confidence=confidence,
                grounding=grounding_score,
                min_required=self._min_confidence,
            )
            return ValidationResult(
                is_valid=False,
                confidence=confidence,
                safe_response=LOW_CONFIDENCE_RESPONSE,
                reason=f"Confidence {confidence:.2f} below threshold {self._min_confidence}",
            )

        if self._require_citations and not has_citations:
            logger.warning("guardrail_missing_citations")
            return ValidationResult(
                is_valid=True,  # Allow but note
                confidence=confidence * 0.8,
                reason="Answer missing citations",
            )

        return ValidationResult(is_valid=True, confidence=confidence)

    def _compute_grounding_score(
        self, answer: str, chunks: list[SearchResult]
    ) -> float:
        """Rough lexical overlap between answer and retrieved context."""
        if not chunks:
            return 0.0
        answer_tokens = set(re.findall(r"\b\w{4,}\b", answer.lower()))
        if not answer_tokens:
            return 0.0
        chunk_tokens = set()
        for chunk in chunks:
            chunk_tokens.update(re.findall(r"\b\w{4,}\b", chunk.text.lower()))
        if not chunk_tokens:
            return 0.0
        overlap = answer_tokens & chunk_tokens
        return len(overlap) / len(answer_tokens)

    def _compute_confidence(
        self,
        grounding_score: float,
        retrieval_score: float,
        has_citations: bool,
    ) -> float:
        score = (grounding_score * 0.5) + (retrieval_score * 0.4) + (0.1 if has_citations else 0.0)
        return round(min(max(score, 0.0), 1.0), 3)
