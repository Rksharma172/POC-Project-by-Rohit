# AskPolicy — Architecture Overview

## System Design

```
┌─────────────┐     ┌──────────────────────────────────────────────┐
│  User/UI    │────▶│              FastAPI Application              │
└─────────────┘     │                                              │
                    │  POST /api/v1/documents/upload               │
                    │  POST /api/v1/chat/query                     │
                    │  GET  /api/v1/documents                      │
                    └──────────────────┬───────────────────────────┘
                                       │
              ┌────────────────────────┼─────────────────────────┐
              │                        │                         │
              ▼                        ▼                         ▼
  ┌─────────────────┐    ┌─────────────────────┐    ┌────────────────┐
  │ DocumentService │    │    ChatService       │    │  Redis Cache   │
  │                 │    │                      │    │                │
  │ - Upload        │    │ - Cache lookup       │    │ - Response     │
  │ - List          │    │ - RAG pipeline call  │    │ - Embedding    │
  │ - Delete        │    │ - Cache store        │    │ - Retrieval    │
  └────────┬────────┘    └──────────┬───────────┘    └────────────────┘
           │                        │
           ▼                        ▼
  ┌─────────────────┐    ┌─────────────────────────────────────────┐
  │  IngestionSvc   │    │              RAG Pipeline                │
  │                 │    │                                         │
  │ 1. Validate     │    │ 1. Embed question                       │
  │ 2. Dup detect   │    │ 2. Hybrid search (semantic + BM25)      │
  │ 3. Parse        │    │ 3. Re-rank (optional)                   │
  │ 4. Chunk        │    │ 4. Build prompt                         │
  │ 5. Embed        │    │ 5. LLM completion                       │
  │ 6. Store        │    │ 6. Guardrails validation                │
  └────────┬────────┘    └──────────┬──────────────────────────────┘
           │                        │
     ┌─────┴──────┐          ┌──────┴──────┐
     │            │          │             │
     ▼            ▼          ▼             ▼
  ┌──────┐  ┌──────────┐  ┌──────┐  ┌──────────┐
  │SQLite│  │ ChromaDB │  │ LLM  │  │Embeddings│
  │ (DB) │  │(VectorDB)│  │ API  │  │   API    │
  └──────┘  └──────────┘  └──────┘  └──────────┘
```

## Provider Abstraction

All external services implement a base interface. Switching providers
requires only a `config.yaml` change — zero business logic changes.

| Component  | Interface               | Current      | Alternatives             |
|------------|------------------------|--------------|--------------------------|
| LLM        | `BaseLLMProvider`       | OpenAI       | Azure, Anthropic, Ollama |
| Embeddings | `BaseEmbeddingProvider` | OpenAI       | BGE, E5 (local)          |
| Vector DB  | `BaseVectorStore`       | ChromaDB     | Pinecone, Weaviate, FAISS|
| Database   | `BaseRepository`        | SQLite       | PostgreSQL               |
| Cache      | `RedisCache`            | Redis        | In-memory (dev)          |

## Duplicate Detection (3 layers)

```
New Document
    │
    ├─ Layer 1: SHA256(file bytes)         ──▶ exact byte match
    │
    ├─ Layer 2: SHA256(normalize(text))    ──▶ same content, different format
    │
    └─ Layer 3: cosine_sim(embedding)      ──▶ near-duplicate / re-upload
                threshold: 0.95 (configurable)
```

## RAG Query Flow

```
User Question
    │
    ├─ 1. Check Redis cache (question + corpus fingerprint)
    │         HIT  → return cached response
    │         MISS → continue
    │
    ├─ 2. Embed question (EmbeddingProvider)
    │
    ├─ 3. Hybrid Search
    │         Semantic: vector similarity (ChromaDB)
    │         BM25:     keyword matching (rank-bm25)
    │         Merge:    Reciprocal Rank Fusion (RRF)
    │
    ├─ 4. Optional Re-rank (BGE Cross-Encoder)
    │
    ├─ 5. Prompt Assembly
    │         System: role + context chunks
    │         User:   question + citation instructions
    │
    ├─ 6. LLM Completion (LLMProvider)
    │
    ├─ 7. Guardrails
    │         - Grounding check (lexical overlap)
    │         - Citations present
    │         - Confidence threshold
    │
    └─ 8. Cache response + return
```

## Configuration-Driven Provider Switching

To switch from GPT-4o-mini to Qwen2.5-7B via Ollama:
```yaml
llm:
  provider: ollama   # was: openai
  model: qwen2.5:7b  # was: gpt-4o-mini
```

To switch from OpenAI embeddings to BGE-base:
```yaml
embeddings:
  provider: bge      # was: openai
  model: BAAI/bge-base-en-v1.5
  dimensions: 768    # was: 1536
  device: cuda
```

To switch from ChromaDB to Pinecone:
```yaml
vectordb:
  provider: pinecone  # was: chromadb
  pinecone_index: policy-docs
  pinecone_environment: us-east-1-aws
```
