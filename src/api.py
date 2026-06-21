import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import shutil
import requests
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from src.retrieval.retriever import retrieve
from src.retrieval.generator import generate_answer
from src.cache.redis_cache import (
    get_cached_answer, set_cached_answer,
    clear_cache, get_cache_stats,
    cache_client, REDIS_AVAILABLE
)

# OLLAMA_HOST   = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")   # for docker container
OLLAMA_HOST   = os.getenv("OLLAMA_URL", "http://localhost:11434")   # for localhost
OLLAMA_MODEL  = "qwen2.5:7b"          # ← 7b model for this GPU laptop
UPLOAD_FOLDER = "documents"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = FastAPI(title="AskPolicy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.mount("/static", StaticFiles(directory="templates"), name="static")


class QuestionRequest(BaseModel):
    question: str


def call_ollama(prompt: str, timeout: int = 60) -> str:
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "top_p": 0.9}
            },
            timeout=timeout
        )
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        return ""
    except Exception as e:
        print(f"  Ollama error: {e}")
        return ""


def is_ollama_available():
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def clear_suggestions_cache():
    try:
        if REDIS_AVAILABLE:
            cache_client.delete("askpolicy:suggestions")
            print("  Cleared cached suggestions")
    except Exception as e:
        print(f"  Could not clear suggestions cache: {e}")


@app.get("/")
def home():
    return {"status": "AskPolicy API running"}


@app.get("/chat")
def chat_ui():
    return FileResponse("templates/index.html")


@app.get("/health")
def health_check():
    return {"status": "healthy", "api": "running", "model": OLLAMA_MODEL}


@app.post("/ask")
def ask_question(request: QuestionRequest):
    print(f"\nQuestion: {request.question}")

    cached = get_cached_answer(request.question)
    if cached:
        print("  Returning cached answer")
        followup = get_single_followup(request.question, cached["answer"])
        return {
            "answer": cached["answer"],
            "sources": cached["sources"],
            "cached": True,
            "followup": followup
        }

    print("  Searching ChromaDB...")
    chunks = retrieve(request.question, top_k=5)

    if not chunks:
        return {
            "answer": "I could not find relevant information in the uploaded documents.",
            "sources": [],
            "cached": False,
            "followup": None
        }

    RELEVANCE_THRESHOLD = 1.0
    relevant_chunks = [c for c in chunks if c.get("distance", 0) < RELEVANCE_THRESHOLD]

    print(f"  {len(chunks)} chunks retrieved, {len(relevant_chunks)} passed relevance filter")
    for c in chunks:
        print(f"     distance={c.get('distance', 'N/A'):.4f} source={c['source']}")

    if not relevant_chunks:
        return {
            "answer": "I don't know based on provided documents",
            "sources": [],
            "cached": False,
            "followup": None
        }

    print("  Generating answer with Qwen 2.5:7b...")
    answer  = generate_answer(request.question, relevant_chunks)
    sources = list(set(c["source"] for c in relevant_chunks))

    if "i don't know" in answer.lower() or "i do not know" in answer.lower():
        sources = []

    followup = get_single_followup(request.question, answer) if sources else None

    if sources:
        set_cached_answer(request.question, answer, sources)

    return {
        "answer": answer,
        "sources": sources,
        "cached": False,
        "followup": followup
    }


def get_single_followup(question: str, answer: str) -> str:
    prompt = f"""Based on this Q&A about company policy,
generate exactly ONE follow-up question starting with
"Would you like to know more about"

Question: {question}
Answer: {answer[:200]}

Rules:
- Must start with "Would you like to know more about"
- Max 15 words total
- Return ONLY the question nothing else"""

    result = call_ollama(prompt, timeout=30)

    if result and "would you like" in result.lower():
        lines = [l.strip() for l in result.split("\n") if l.strip() and len(l.strip()) > 5]
        if lines:
            return lines[0]

    topic = question.lower().replace("what is", "").replace("what are", "")\
        .replace("how do i", "").replace("how", "").strip()
    return f"Would you like to know more about {topic}?"


def get_document_groups():
    from src.vectordb.chroma_manager import get_collection
    col = get_collection()
    count = col.count()

    if count == 0:
        return {}

    all_data = col.get()
    docs  = all_data.get("documents", [])
    metas = all_data.get("metadatas", [])

    doc_chunks = {}
    for doc, meta in zip(docs, metas):
        source = meta.get("source", "unknown") if meta else "unknown"
        if source not in doc_chunks:
            doc_chunks[source] = []
        doc_chunks[source].append(doc)

    return doc_chunks


@app.get("/suggestions")
def get_suggestions():
    try:
        if REDIS_AVAILABLE:
            cached = cache_client.get("askpolicy:suggestions")
            if cached:
                print("  Returning cached suggestions")
                return json.loads(cached)
    except Exception as e:
        print(f"  Suggestion cache check failed: {e}")

    if not is_ollama_available():
        print("  Ollama not reachable — returning defaults without trying")
        return {"suggestions": get_default_suggestions(), "source": "ollama_unavailable"}

    doc_chunks = get_document_groups()

    if not doc_chunks:
        print("  No documents in ChromaDB — using defaults")
        return {"suggestions": get_default_suggestions(), "source": "default"}

    unique_sources = list(doc_chunks.keys())
    num_docs = len(unique_sources)
    print(f"\n  Found {num_docs} document(s): {unique_sources}")

    TOTAL_SUGGESTIONS = 5

    if num_docs >= TOTAL_SUGGESTIONS:
        distribution = {src: 1 for src in unique_sources[:TOTAL_SUGGESTIONS]}
    else:
        base = TOTAL_SUGGESTIONS // num_docs
        remainder = TOTAL_SUGGESTIONS % num_docs
        distribution = {}
        for idx, src in enumerate(unique_sources):
            distribution[src] = base + (1 if idx < remainder else 0)

    print(f"  Distribution plan: {distribution}")

    suggestions = []

    for source, num_questions in distribution.items():
        chunks = doc_chunks[source]
        if not chunks:
            continue

        print(f"  Generating {num_questions} question(s) for: {source}")

        sample_chunks = chunks[:min(8, len(chunks))]
        generated_for_doc = 0
        attempt = 0
        max_attempts = num_questions + 2

        while generated_for_doc < num_questions and attempt < max_attempts:
            attempt += 1
            start_idx = (attempt * 2) % max(len(sample_chunks), 1)
            content_slice = sample_chunks[start_idx:start_idx + 2] or sample_chunks[:2]
            sample_text = "\n".join(content_slice)[:500]

            if not sample_text.strip():
                continue

            prompt = f"""Based on this content, generate ONE short question.

CONTENT:
{sample_text}

Rules:
- Max 12 words
- Return ONLY the question
- No numbering"""

            result = call_ollama(prompt, timeout=45)

            if result:
                question = result.strip().split("\n")[0].strip()
                question = question.lstrip("0123456789.-) \"'").rstrip("\"'")

                if len(question) > 5 and "?" in question and question not in suggestions:
                    suggestions.append(question)
                    generated_for_doc += 1
                    print(f"     [{source}] {question}")
            else:
                print(f"     Ollama call failed for {source}, attempt {attempt}")

    print(f"  Final suggestions count: {len(suggestions)}")

    if len(suggestions) == 0:
        result = {"suggestions": get_default_suggestions(), "source": "default"}
    else:
        result = {"suggestions": suggestions[:TOTAL_SUGGESTIONS], "source": "documents"}

    try:
        if REDIS_AVAILABLE:
            cache_client.setex("askpolicy:suggestions", 3600, json.dumps(result))
            print("  Suggestions cached for future requests")
    except Exception as e:
        print(f"  Could not cache suggestions: {e}")

    return result


def get_default_suggestions():
    return [
        "What is the annual leave policy?",
        "What are the travel expense limits?",
        "What is the work from home policy?",
        "What are the office timings?",
        "How do I apply for sick leave?"
    ]


@app.get("/debug/sources")
def debug_sources():
    doc_chunks = get_document_groups()
    summary = {src: len(chunks) for src, chunks in doc_chunks.items()}
    return {"total_documents": len(doc_chunks), "chunks_per_document": summary}


@app.get("/debug/ollama")
def debug_ollama():
    import time
    available = is_ollama_available()
    if not available:
        return {"ollama_reachable": False}

    start = time.time()
    result = call_ollama("Say hello in one word.", timeout=60)
    elapsed = time.time() - start

    return {
        "ollama_reachable": True,
        "response": result,
        "elapsed_seconds": round(elapsed, 2)
    }


@app.get("/followup")
def get_followup(question: str, answer: str):
    followup = get_single_followup(question, answer)
    return {"followup": followup}


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        allowed = [".pdf", ".docx", ".xlsx", ".csv", ".html", ".txt", ".md"]
        ext = os.path.splitext(file.filename)[1].lower()

        if ext not in allowed:
            return {"success": False, "message": f"File type {ext} not supported."}

        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        print(f"\n  Saved: {file.filename}")

        all_files = os.listdir(UPLOAD_FOLDER)
        print(f"  All files now: {all_files}")

        from src.vectordb.chroma_manager import clear_db, store_chunks, verify_db
        clear_db()

        from src.ingestion.parsers.parser_router import load_documents
        from src.ingestion.chunker import chunk_documents

        docs = load_documents(UPLOAD_FOLDER)
        print(f"  Loaded {len(docs)} documents total")

        if not docs:
            return {"success": False, "message": "No documents could be parsed."}

        chunks = chunk_documents(docs)
        print(f"  Created {len(chunks)} chunks")

        store_chunks(chunks)
        verify_db()
        clear_cache()
        clear_suggestions_cache()

        doc_chunks = get_document_groups()
        print(f"  Chunks per document: { {k: len(v) for k, v in doc_chunks.items()} }")

        return {
            "success": True,
            "message": f"{file.filename} uploaded! {len(chunks)} chunks from {len(docs)} documents.",
            "chunks_created": len(chunks),
            "total_documents": len(docs),
            "all_files": all_files
        }

    except Exception as e:
        print(f"  Upload error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"Upload failed: {str(e)}"}


@app.get("/documents")
def list_documents():
    try:
        files = []
        for file in os.listdir(UPLOAD_FOLDER):
            path = os.path.join(UPLOAD_FOLDER, file)
            if os.path.isfile(path):
                size = os.path.getsize(path)
                files.append({"name": file, "size_kb": round(size / 1024, 1)})
        return {"documents": files}
    except Exception as e:
        return {"documents": [], "error": str(e)}


@app.delete("/documents/{filename}")
def delete_document(filename: str):
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(file_path):
            return {"success": False, "message": f"File {filename} not found"}

        os.remove(file_path)
        print(f"\n  Deleted: {filename}")

        from src.ingestion.parsers.parser_router import load_documents
        from src.ingestion.chunker import chunk_documents
        from src.vectordb.chroma_manager import store_chunks, clear_db

        clear_db()
        docs = load_documents(UPLOAD_FOLDER)

        if docs:
            chunks = chunk_documents(docs)
            store_chunks(chunks)
            print(f"  Re-ingested {len(chunks)} chunks")
        else:
            print("  No documents remaining")

        clear_cache()
        clear_suggestions_cache()

        return {"success": True, "message": f"{filename} deleted"}

    except Exception as e:
        print(f"  Delete error: {e}")
        return {"success": False, "message": f"Delete failed: {str(e)}"}


@app.get("/cache/stats")
def cache_stats():
    return get_cache_stats()


@app.delete("/cache/clear")
def clear_all_cache():
    clear_cache()
    return {"message": "Cache cleared"}