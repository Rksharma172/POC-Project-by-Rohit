from __future__ import annotations


class AskPolicyError(Exception):
    """Base error for all application exceptions."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


# ── Document Errors ───────────────────────────────────────────────────────────

class DocumentNotFoundError(AskPolicyError):
    status_code = 404
    error_code = "DOCUMENT_NOT_FOUND"


class DocumentAlreadyExistsError(AskPolicyError):
    status_code = 409
    error_code = "DOCUMENT_DUPLICATE"


class DocumentParseError(AskPolicyError):
    status_code = 422
    error_code = "DOCUMENT_PARSE_ERROR"


class UnsupportedFileTypeError(AskPolicyError):
    status_code = 415
    error_code = "UNSUPPORTED_FILE_TYPE"


class FileTooLargeError(AskPolicyError):
    status_code = 413
    error_code = "FILE_TOO_LARGE"


# ── RAG / LLM Errors ──────────────────────────────────────────────────────────

class LLMProviderError(AskPolicyError):
    status_code = 502
    error_code = "LLM_PROVIDER_ERROR"


class EmbeddingError(AskPolicyError):
    status_code = 502
    error_code = "EMBEDDING_ERROR"


class VectorStoreError(AskPolicyError):
    status_code = 502
    error_code = "VECTOR_STORE_ERROR"


class RetrievalError(AskPolicyError):
    status_code = 500
    error_code = "RETRIEVAL_ERROR"


class GuardrailViolationError(AskPolicyError):
    status_code = 422
    error_code = "GUARDRAIL_VIOLATION"


# ── Cache Errors ──────────────────────────────────────────────────────────────

class CacheError(AskPolicyError):
    status_code = 503
    error_code = "CACHE_ERROR"


# ── Configuration Errors ──────────────────────────────────────────────────────

class ConfigurationError(AskPolicyError):
    status_code = 500
    error_code = "CONFIGURATION_ERROR"


class ProviderNotSupportedError(ConfigurationError):
    error_code = "PROVIDER_NOT_SUPPORTED"
