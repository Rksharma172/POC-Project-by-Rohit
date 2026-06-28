# AskPolicy

AskPolicy is an internal policy-document Q&A app. Users upload HR, IT, finance, or operations documents, then ask questions against only the documents available to their account.

## What Is Included

- Table-aware parsing and chunking for DOCX, XLSX, CSV, and table-like content.
- Hybrid retrieval: vector search plus lexical matching and reranking.
- Evidence validation before answers, follow-ups, and suggestions are accepted.
- Background upload/delete processing with visible job status in the UI.
- Shared Ollama model configuration for answers and suggestions.
- Lightweight login with per-user document separation.
- Docker Compose setup for API + Redis.

## Local Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
ollama pull qwen2.5:7b
python -m uvicorn src.api:app --reload --port 8000
```

Open:

```text
http://localhost:8000/chat
```

Redis is optional for basic use, but recommended for answer and suggestion caching.

## Demo Login

Default demo users are configured in `config.yaml`. These are meant for local testing only, especially for checking per-user document separation:

| User | Password |
|------|----------|
| hr | hr-demo |
| finance | finance-demo |
| admin | admin-demo |

Each logged-in user sees only their own uploaded documents and vector chunks. The unauthenticated `default` user remains available for quick local demos.

Do not use the demo passwords in production. For safer deployments, either override them with environment variables or replace the lightweight demo login with database-backed users, hashed passwords, and proper session management.

To override demo passwords with environment variables:

```text
ASKPOLICY_USER_HR_PASSWORD=change-this
ASKPOLICY_USER_FINANCE_PASSWORD=change-this
ASKPOLICY_USER_ADMIN_PASSWORD=change-this
```

## Docker

Start Ollama on the host first:

```bash
ollama serve
```

Then run:

```bash
docker compose up --build
```

Docker Compose sets:

```text
REDIS_HOST=redis
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_SUGGESTION_MODEL=qwen2.5:7b
```

Open:

```text
http://localhost:8000/chat
```

## Cloud Hosting Notes

For a cloud deployment:

1. Run the FastAPI container from `Dockerfile`.
2. Use managed Redis or the Redis service from `docker-compose.yml`.
3. Mount persistent volumes for `documents/` and `chroma_db/`.
4. Set strong `ASKPOLICY_USER_*_PASSWORD` values.
5. Point `OLLAMA_URL` to a reachable Ollama host or replace the generator layer with a hosted model provider.
6. Put the app behind HTTPS and an organization SSO/reverse proxy for production use.

## Main Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/login` | Create a lightweight UI session |
| GET | `/chat` | Web UI |
| POST | `/ask` | Ask a question |
| POST | `/upload` | Upload and start background processing |
| GET | `/jobs/latest` | Latest upload/delete job for current user |
| GET | `/jobs/{job_id}` | Processing status |
| GET | `/documents` | List current user's documents |
| DELETE | `/documents/{name}` | Delete and reindex |
| GET | `/suggestions` | Evidence-validated suggested questions |
| GET | `/health` | Health and model configuration |

## Configuration

Important settings live in `config.yaml`:

```yaml
retrieval:
  top_k: 5
  candidate_k: 24
  vector_weight: 0.68
  lexical_weight: 0.32
  max_distance: 0.95

generation:
  answer_model: "qwen2.5:7b"
  suggestion_model: "qwen2.5:7b"
```

Environment variables override the model choices:

```text
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_SUGGESTION_MODEL=qwen2.5:7b
REDIS_HOST=localhost
```

## Supported Files

- PDF, including OCR fallback when Poppler and Tesseract are installed.
- DOCX.
- XLSX, XLS, CSV.
- HTML, HTM.
- TXT, MD.
