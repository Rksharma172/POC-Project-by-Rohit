from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── Request metrics ────────────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "askpolicy_requests_total",
    "Total number of API requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "askpolicy_request_latency_seconds",
    "Request latency in seconds",
    ["endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# ── RAG metrics ────────────────────────────────────────────────────────────────
RAG_QUERY_COUNT = Counter(
    "askpolicy_rag_queries_total",
    "Total RAG queries",
    ["status"],
)

RAG_LATENCY = Histogram(
    "askpolicy_rag_latency_seconds",
    "RAG pipeline latency",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

RAG_CONFIDENCE = Histogram(
    "askpolicy_rag_confidence",
    "RAG answer confidence scores",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# ── Cache metrics ──────────────────────────────────────────────────────────────
CACHE_HIT = Counter(
    "askpolicy_cache_hits_total",
    "Cache hits by type",
    ["cache_type"],
)

CACHE_MISS = Counter(
    "askpolicy_cache_misses_total",
    "Cache misses by type",
    ["cache_type"],
)

# ── LLM cost tracking ──────────────────────────────────────────────────────────
LLM_TOKENS_USED = Counter(
    "askpolicy_llm_tokens_total",
    "Total LLM tokens used",
    ["token_type"],  # prompt | completion
)

LLM_COST_ESTIMATE = Counter(
    "askpolicy_llm_cost_usd_total",
    "Estimated LLM cost in USD",
)

# ── Document metrics ───────────────────────────────────────────────────────────
DOCUMENTS_INGESTED = Counter(
    "askpolicy_documents_ingested_total",
    "Documents ingested",
    ["status"],
)

DOCUMENT_COUNT = Gauge(
    "askpolicy_document_count",
    "Current number of documents in the system",
)

# ── Error metrics ──────────────────────────────────────────────────────────────
ERROR_COUNT = Counter(
    "askpolicy_errors_total",
    "Total errors",
    ["error_code"],
)


def record_rag_query(
    latency_ms: float,
    confidence: float,
    token_usage: dict,
    cache_hit: bool,
    cost_per_1k_input: float = 0.00015,
    cost_per_1k_output: float = 0.0006,
) -> None:
    RAG_QUERY_COUNT.labels(status="success").inc()
    RAG_LATENCY.observe(latency_ms / 1000)
    RAG_CONFIDENCE.observe(confidence)

    if cache_hit:
        CACHE_HIT.labels(cache_type="response").inc()
    else:
        CACHE_MISS.labels(cache_type="response").inc()

    prompt_tokens = token_usage.get("prompt_tokens", 0)
    completion_tokens = token_usage.get("completion_tokens", 0)
    if prompt_tokens:
        LLM_TOKENS_USED.labels(token_type="prompt").inc(prompt_tokens)
        LLM_COST_ESTIMATE.inc((prompt_tokens / 1000) * cost_per_1k_input)
    if completion_tokens:
        LLM_TOKENS_USED.labels(token_type="completion").inc(completion_tokens)
        LLM_COST_ESTIMATE.inc((completion_tokens / 1000) * cost_per_1k_output)
