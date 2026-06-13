# AskPolicy — Internal Policy Q&A

> Enterprise RAG system for HR policies, SOPs, and compliance documents.
> Employees upload documents, ask questions, and get grounded answers with citations.

---

## Quick Start

### Prerequisites
- Docker Desktop installed
- Ollama installed

### 1. Clone the repo
```bash
git clone https://github.com/yourname/AskPolicy.git
cd AskPolicy
```

### 2. Pull Qwen model
```bash
ollama pull qwen2.5:7b
```

### 3. Start Ollama
```bash
ollama serve
```

### 4. Start Docker
```bash
docker-compose up --build
```

### 5. Open Browser
```
http://localhost:8000/chat
```

---

## Architecture

```
Employee Question
      ↓
Frontend (HTML + CSS + JS)
      ↓
FastAPI Backend (port 8000)
      ↓
Redis Cache (check first)
      ↓
BGE Embeddings (384 dimensions)
      ↓
ChromaDB Vector Search
      ↓
Qwen 2.5:7b via Ollama
      ↓
Answer + Citations + Follow-ups
```

---

## Project Structure

```
AskPolicy/
├── Dockerfile
├── docker-compose.yml
├── config.yaml
├── requirements.txt
├── documents/              ← put PDFs here
├── chroma_db/              ← auto created
├── templates/
│   ├── index.html          ← UI structure
│   ├── style.css           ← UI styles
│   └── app.js              ← UI logic
└── src/
    ├── api.py              ← FastAPI backend
    ├── config_loader.py    ← reads config.yaml
    ├── ingest_pipeline.py  ← manual ingestion
    ├── ingestion/
    │   ├── chunker.py      ← splits text
    │   ├── embedder.py     ← text to numbers
    │   └── parsers/
    │       ├── parser_router.py
    │       ├── pdf_parser.py
    │       ├── docx_parser.py
    │       ├── excel_parser.py
    │       ├── html_parser.py
    │       └── text_parser.py
    ├── vectordb/
    │   └── chroma_manager.py
    ├── retrieval/
    │   ├── retriever.py    ← searches ChromaDB
    │   ├── generator.py    ← calls Qwen
    │   └── rag_pipeline.py
    └── cache/
        └── redis_cache.py
```

---

## Configuration

All settings in `config.yaml`:

```yaml
embeddings:
  provider: "bge"           # free local model

chunking:
  strategy: "semantic"      # smart chunking
  chunk_size: 512

cache:
  ttl_seconds: 3600         # 1 hour cache
```

---

## Supported File Types

| Type  | Extension          |
|-------|--------------------|
| PDF   | .pdf               |
| Word  | .docx              |
| Excel | .xlsx, .csv        |
| HTML  | .html              |
| Text  | .txt, .md          |

---

## API Endpoints

| Method | Endpoint          | Description          |
|--------|-------------------|----------------------|
| GET    | /chat             | Chat UI              |
| POST   | /ask              | Ask a question       |
| POST   | /upload           | Upload document      |
| GET    | /documents        | List documents       |
| DELETE | /documents/{name} | Delete document      |
| GET    | /cache/stats      | Cache statistics     |
| DELETE | /cache/clear      | Clear cache          |

---

## Tech Stack

| Component  | Technology              |
|------------|-------------------------|
| Frontend   | HTML + CSS + JavaScript |
| Backend    | FastAPI (Python)        |
| Embeddings | BGE small (free)        |
| Vector DB  | ChromaDB                |
| LLM        | Qwen 2.5:7b via Ollama  |
| Cache      | Redis 7                 |
| Container  | Docker                  |

---

## Cost

```
100% FREE
→ No API keys needed
→ Runs completely locally
→ Data never leaves your machine
```

---

## Daily Usage

```bash
# Start
ollama serve
docker-compose up

# Stop
docker-compose down
taskkill /F /IM ollama.exe   # Windows
```

---

## Scale to Production

| Component  | POC          | Production        |
|------------|--------------|-------------------|
| LLM        | Qwen local   | OpenAI API        |
| Vector DB  | ChromaDB     | Pinecone          |
| Cache      | Redis local  | Redis Cloud       |
| Deploy     | Docker local | AWS/Azure         |
| Users      | 1-5          | 1000+             |

---

*Built with FastAPI · ChromaDB · BGE · Qwen 2.5 · Redis · Docker*