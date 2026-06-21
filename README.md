# 🏢 AskPolicy — Internal Policy Q&A

> RAG system for HR policies. Upload documents, ask questions, get cited answers.
> 100% Free · Runs Locally · No API Keys Needed

---

## 📋 Prerequisites (Install Once)

| Tool | Download | Required For |
|------|----------|---------------|
| Python 3.11 | https://www.python.org/downloads | Local setup only |
| Ollama | https://ollama.com/download | Both setups |
| Memurai (Redis for Windows) | https://www.memurai.com/get-memurai | Local setup only |
| Docker Desktop | https://www.docker.com/products/docker-desktop | Docker setup only |

### Pull the Qwen Model (One Time Only)
```bash
ollama pull qwen2.5:3b
```
*(Use `qwen2.5:7b` instead if you have a GPU laptop)*

---

# 🐳 OPTION 1: Run with Docker

**Best for:** sharing the project, demos, consistent environment across machines
**Downside:** uses 4-7 GB RAM, can slow down weaker laptops

## Docker Setup — One Time Only

1. Install Docker Desktop and open it
2. Make sure `config.yaml` has:
```yaml
   cache:
     host: "redis"
```
3. Make sure `generator.py` and `api.py` have:
```python
   OLLAMA_HOST = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
```
4. Make sure `docker-compose.yml` has:
```yaml
   extra_hosts:
     - "host.docker.internal:host-gateway"
```

## Docker — Daily Run Steps

```bash
# Step 1: Start Ollama (separate terminal)
ollama serve

# Step 2: Start Docker
cd AskPolicy
docker-compose up --build

# Step 3: Open browser
http://localhost:8000/chat
```

## Docker — Stop

```bash
docker-compose down
```

---

# 💻 OPTION 2: Run Locally (No Docker)

**Best for:** daily development, low-RAM laptops, avoiding Docker overhead
**Uses:** ~1 GB RAM total

## Local Setup — One Time Only

### Step 1: Update `config.yaml`
```yaml
cache:
  host: "localhost"
```

### Step 2: Update `src/retrieval/generator.py`
```python
OLLAMA_HOST = os.getenv("OLLAMA_URL", "http://localhost:11434")
```

### Step 3: Update `src/api.py`
```python
OLLAMA_HOST = os.getenv("OLLAMA_URL", "http://localhost:11434")
```

### Step 4: Create Virtual Environment
```bash
cd AskPolicy
python -m venv venv
venv\Scripts\activate
```

### Step 5: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 6: Install Memurai (Redis for Windows)
```
1. Download: https://www.memurai.com/get-memurai
2. Run installer
3. It auto-starts as a Windows Service
```

### Step 7: Verify Memurai Is Running
```bash
venv\Scripts\activate
python -c "import redis; r = redis.Redis(host='localhost', port=6379); print(r.ping())"
```
Should print `True` ✅

If it errors:
```
Press Windows key → "Services" → find "Memurai" → Start
```

## Local — Daily Run Steps (Every Time)

### Terminal 1 — Ollama
```bash
ollama serve
```
*(skip if already running — check with `http://localhost:11434`)*

### Terminal 2 — FastAPI
```bash
cd AskPolicy
venv\Scripts\activate
python -m uvicorn src.api:app --reload --port 8000
```

### Browser
```
http://localhost:8000/chat
```

## Local — Stop

```bash
Press Ctrl + C in Terminal 2 (stops FastAPI)
Ollama and Memurai can keep running in background
```

---

## 🔄 Switching Between Docker and Local

| File | Docker Value | Local Value |
|------|--------------|--------------|
| `config.yaml` → `cache.host` | `"redis"` | `"localhost"` |
| `generator.py` → `OLLAMA_HOST` default | `http://host.docker.internal:11434` | `http://localhost:11434` |
| `api.py` → `OLLAMA_HOST` default | `http://host.docker.internal:11434` | `http://localhost:11434` |

**Tip:** Keep two copies of `config.yaml` (`config.docker.yaml` and `config.local.yaml`) and swap them when switching modes, instead of editing the same file repeatedly.

---

## 📁 Project Structure

```
AskPolicy/
├── Dockerfile
├── docker-compose.yml
├── config.yaml
├── requirements.txt
├── documents/               ← uploaded files stored here
├── chroma_db/                ← vector database (auto created)
├── templates/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── src/
    ├── api.py
    ├── config_loader.py
    ├── ingest_pipeline.py
    ├── ingestion/
    │   ├── chunker.py
    │   ├── embedder.py
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
    │   ├── retriever.py
    │   └── generator.py
    └── cache/
        └── redis_cache.py
```

---

## ⚙️ Configuration Reference

```yaml
embeddings:
  provider: "bge"
  model: "BAAI/bge-small-en-v1.5"
  batch_size: 32

chunking:
  strategy: "semantic"
  chunk_size: 512
  chunk_overlap: 50
  min_chunk_size: 100

cache:
  ttl_seconds: 3600
  embedding_ttl: 86400
```

---

## 📄 Supported File Types

| Type | Extension |
|------|-----------|
| PDF | .pdf |
| Word | .docx |
| Excel | .xlsx .csv |
| HTML | .html |
| Text | .txt .md |

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/chat` | Chat UI |
| POST | `/ask` | Ask a question |
| POST | `/upload` | Upload document |
| GET | `/documents` | List documents |
| DELETE | `/documents/{name}` | Delete document |
| GET | `/suggestions` | Get 5 suggested questions |
| GET | `/followup` | Get follow-up suggestion |
| GET | `/cache/stats` | Redis cache stats |
| DELETE | `/cache/clear` | Clear cache |
| GET | `/debug/sources` | Show chunks per document |
| GET | `/debug/ollama` | Test Ollama connectivity/speed |
| GET | `/health` | Health check |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | HTML + CSS + JavaScript |
| Backend | FastAPI (Python) |
| Embeddings | BGE small (free, local) |
| Vector DB | ChromaDB |
| LLM | Qwen 2.5 (3B or 7B) via Ollama |
| Cache | Redis / Memurai |
| Container (optional) | Docker |

---

## ❗ Common Problems & Fixes

| Problem | Fix |
|---------|-----|
| `redis-cli not recognized` | You have Memurai — use `memurai-cli ping` instead |
| Redis/Memurai connection error | Open Services → start "Memurai" |
| Ollama connection timeout | Check `ollama serve` is running; visit `http://localhost:11434` |
| Model not found | Run `ollama pull qwen2.5:3b` |
| Suggestions always show defaults | Check `/debug/sources` and `/debug/ollama` to isolate the issue |
| ChromaDB shows 0 or 1 chunk per large document | Chunker fallback bug — already fixed in `chunker.py` |
| Docker laptop hangs / too slow | Switch to Local setup (Option 2) |
| Port 8000 already in use | `netstat -ano \| findstr :8000` then `taskkill /PID <PID> /F` |

---

## 💰 Cost

```
100% FREE
→ No API keys required
→ Runs entirely on your machine
→ No data leaves your network
```

---

## 🚀 Quick Start Cheat Sheet

```
DOCKER:
1. ollama serve
2. docker-compose up --build
3. http://localhost:8000/chat

LOCAL:
1. ollama serve
2. venv\Scripts\activate
   python -m uvicorn src.api:app --reload --port 8000
3. http://localhost:8000/chat
```

---

*Built with FastAPI · ChromaDB · BGE · Qwen 2.5 · Redis/Memurai*