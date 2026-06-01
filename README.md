# AskPolicy — Internal Policy Q&A

> Enterprise RAG system for HR policies, SOPs, and compliance documents.  
> Employees upload documents. Employees ask questions. The system answers — grounded, cited, and never hallucinated.

---

## Quick Start

```bash
# 1. Clone and set up environment
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY at minimum

# 2. Install dependencies
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Run the API
uvicorn app.main:app --reload --port 8000

# 4. Seed sample documents
python scripts/seed_documents.py

# 5. Ask a question
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many days of annual leave do I get?"}'
```

**Or with Docker:**
```bash
docker-compose up --build
```

---

## Architecture

```
User Question
  → Redis Cache check
  → Embed question (OpenAI / BGE / E5)
  → Hybrid Search (Semantic + BM25, merged via RRF)
  → Optional Re-rank (BGE Cross-Encoder)
  → Prompt Builder (system prompt + retrieved context)
  → LLM Completion (OpenAI / Azure / Anthropic / Ollama)
  → Guardrails (grounding + citations + confidence)
  → Cached Response
```

See [docs/architecture.md](docs/architecture.md) for full diagrams and provider-switching guide.

---

## API Reference

### Upload a Document
```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@leave_policy.pdf" \
  -F "document_name=Annual Leave Policy" \
  -F "department=HR" \
  -F "version=2024-01"
```

### Ask a Question
```bash
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the expense limit for hotel stays?",
    "top_k": 5
  }'
```

**Response:**
```json
{
  "answer": "The hotel expense limit is $250/night in major cities and $180/night elsewhere.",
  "citations": [
    {
      "document": "Expense Reimbursement Policy",
      "document_id": "abc-123",
      "section": "Travel",
      "relevance_score": 0.92
    }
  ],
  "confidence": 0.87,
  "session_id": "sess-xyz",
  "cache_hit": false,
  "latency_ms": 1240
}
```

### List Documents
```bash
curl http://localhost:8000/api/v1/documents
```

### Delete a Document
```bash
curl -X DELETE http://localhost:8000/api/v1/documents/{document_id}
```

### Health Check
```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

### Metrics (Prometheus)
```bash
curl http://localhost:8000/metrics
```

---

## Configuration

All provider settings live in [config.yaml](config.yaml). No code changes needed to switch providers.

### Switch LLM Provider

| Provider     | config.yaml setting                               |
|-------------|---------------------------------------------------|
| OpenAI       | `llm.provider: openai`, `llm.model: gpt-4o-mini`  |
| Azure OpenAI | `llm.provider: azure_openai`                      |
| Anthropic    | `llm.provider: anthropic`                         |
| Ollama/Qwen  | `llm.provider: ollama`, `llm.model: qwen2.5:7b`   |

### Switch Embedding Provider

| Provider | config.yaml setting                                     |
|---------|---------------------------------------------------------|
| OpenAI   | `embeddings.provider: openai`                           |
| BGE      | `embeddings.provider: bge`, `embeddings.dimensions: 768`|
| E5       | `embeddings.provider: e5`                               |

### Switch Vector Database

| Provider  | config.yaml setting            |
|-----------|-------------------------------|
| ChromaDB  | `vectordb.provider: chromadb`  |
| Pinecone  | `vectordb.provider: pinecone`  |
| Weaviate  | `vectordb.provider: weaviate`  |

---

## Project Structure

```
AskPolicy/
├── app/
│   ├── main.py                      # FastAPI app + lifespan wiring
│   ├── api/
│   │   ├── routes/                  # documents.py, chat.py, health.py
│   │   └── middleware/              # Exception handler, request context
│   ├── core/
│   │   ├── config/settings.py       # Pydantic settings + YAML overlay
│   │   ├── exceptions.py            # Typed exception hierarchy
│   │   └── logging.py               # Structured JSON logging (structlog)
│   ├── rag/
│   │   ├── llm/                     # BaseLLMProvider + OpenAI/Azure/Anthropic/Ollama
│   │   ├── embeddings/              # BaseEmbeddingProvider + OpenAI/BGE/E5
│   │   ├── vectordb/                # BaseVectorStore + ChromaDB
│   │   ├── pipeline.py              # Full RAG orchestration
│   │   ├── search.py                # Hybrid search (semantic + BM25 + RRF)
│   │   ├── reranker.py              # BGE cross-encoder re-ranker
│   │   └── guardrails.py            # Anti-hallucination validator
│   ├── ingestion/
│   │   ├── parsers/                 # PDF, DOCX, HTML, TXT parsers
│   │   ├── chunking/chunker.py      # Section-aware chunker
│   │   ├── duplicate_detector.py    # 3-layer duplicate detection
│   │   └── ingestion_service.py     # Full ingestion pipeline
│   ├── services/
│   │   ├── document_service.py      # Document management facade
│   │   └── chat_service.py          # Chat + cache facade
│   ├── repositories/
│   │   └── document_repository.py  # SQLAlchemy async repository
│   ├── cache/redis_cache.py         # Redis cache with key builders
│   ├── workers/tasks.py             # Celery + FastAPI background tasks
│   ├── monitoring/metrics.py        # Prometheus counters/histograms
│   ├── prompts/templates.py         # System + user prompt templates
│   ├── models/document.py           # SQLAlchemy ORM model
│   ├── schemas/                     # Pydantic request/response schemas
│   └── utils/                       # Hash utils, retry decorator
├── tests/
│   ├── unit/                        # Chunker, duplicate detector, guardrails
│   ├── integration/                 # Ingestion pipeline tests
│   └── rag/                         # RAG pipeline tests
├── scripts/
│   ├── seed_documents.py            # Upload sample policies
│   └── health_check.py              # Check all endpoints
├── docs/
│   ├── architecture.md              # System design + diagrams
│   └── prometheus.yml               # Prometheus scrape config
├── config.yaml                      # All provider/model configuration
├── .env.example                     # Environment variable template
├── requirements.txt
├── Dockerfile
├── docker-compose.yml               # API + Worker + Redis + Prometheus + Grafana
└── pytest.ini
```

---

## Running Tests

```bash
pytest                           # all tests with coverage
pytest tests/unit/               # unit tests only
pytest tests/rag/                # RAG pipeline tests
pytest -k "test_chunker"         # specific test
```

---

## Supported File Types

| Type | Extension | Parser        |
|------|-----------|---------------|
| PDF  | .pdf      | PyMuPDF       |
| Word | .docx     | python-docx   |
| HTML | .html     | BeautifulSoup |
| Text | .txt, .md | aiofiles      |

---

## Monitoring

Access after `docker-compose up`:
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **API Docs**: http://localhost:8000/docs
- **Metrics**: http://localhost:8000/metrics

Tracked metrics:
- `askpolicy_rag_queries_total` — query volume
- `askpolicy_rag_latency_seconds` — pipeline latency
- `askpolicy_rag_confidence` — answer confidence distribution
- `askpolicy_cache_hits_total` — cache effectiveness
- `askpolicy_llm_tokens_total` — token usage
- `askpolicy_llm_cost_usd_total` — estimated cost
- `askpolicy_documents_ingested_total` — ingestion volume

---

## Environment Variables

| Variable               | Required | Description                        |
|------------------------|----------|------------------------------------|
| `OPENAI_API_KEY`        | Yes*     | OpenAI API key                     |
| `ANTHROPIC_API_KEY`     | No       | Anthropic API key                  |
| `AZURE_OPENAI_API_KEY`  | No       | Azure OpenAI key                   |
| `REDIS_URL`             | No       | Redis connection URL               |
| `DATABASE_URL`          | No       | SQLAlchemy DB URL (SQLite default) |
| `SECRET_KEY`            | Yes      | App secret key                     |

*Required when `llm.provider: openai` in config.yaml

---

## Production Checklist

- [ ] Replace SQLite with PostgreSQL (`DATABASE_URL=postgresql+asyncpg://...`)
- [ ] Set CORS origins to specific frontend domains in `main.py`
- [ ] Add authentication middleware (JWT / OAuth2)
- [ ] Enable semantic duplicate detection (configure threshold in config.yaml)
- [ ] Configure Celery workers for async ingestion
- [ ] Set `APP_ENV=production` and `APP_DEBUG=false`
- [ ] Set `SECRET_KEY` to a cryptographically random 32-char value
- [ ] Configure Grafana dashboards and alerting rules
- [ ] Enable reranking if quality is prioritized over latency

---

*Built with FastAPI · ChromaDB · OpenAI · Redis · Prometheus*
