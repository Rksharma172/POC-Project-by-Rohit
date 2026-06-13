import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
))

import shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from src.retrieval.retriever import retrieve
from src.retrieval.generator import generate_answer
from src.cache.redis_cache import (
    get_cached_answer,
    set_cached_answer,
    clear_cache,
    get_cache_stats
)

# ── Create FastAPI app FIRST ──────────────────────────────────
app = FastAPI(title="AskPolicy API")

# ── CORS middleware ───────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

UPLOAD_FOLDER = "documents"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ── Models ────────────────────────────────────────────────────
class QuestionRequest(BaseModel):
    question: str


# ── Routes ───────────────────────────────────────────────────

@app.get("/")
def home():
    return {"status": "AskPolicy API running "}


@app.get("/chat")
def chat_ui():
    return FileResponse("templates/index.html")


@app.post("/ask")
def ask_question(request: QuestionRequest):
    print(f"\n❓ Question: {request.question}")

    # Check cache first
    cached = get_cached_answer(request.question)
    if cached:
        suggestions = generate_followups(
            request.question,
            cached["answer"]
        )
        return {
            "answer"     : cached["answer"],
            "sources"    : cached["sources"],
            "cached"     : True,
            "suggestions": suggestions
        }

    # RAG pipeline
    chunks  = retrieve(request.question, top_k=5)
    answer  = generate_answer(request.question, chunks)
    sources = list(set(c["source"] for c in chunks))

    # Generate follow-ups
    suggestions = generate_followups(request.question, answer)

    # Cache answer
    set_cached_answer(request.question, answer, sources)

    return {
        "answer"     : answer,
        "sources"    : sources,
        "cached"     : False,
        "suggestions": suggestions
    }


def generate_followups(question, answer):
    import requests
    try:
        prompt = f"""Based on this Q&A about company policies,
suggest exactly 3 short follow-up questions.

Question: {question}
Answer: {answer[:300]}

Rules:
- Each question max 10 words
- Relevant to the topic
- Return ONLY 3 questions one per line
- No numbering no bullets"""

        response = requests.post(
            "http://host.docker.internal:11434/api/generate",
            json={
                "model" : "qwen2.5:7b",
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )

        if response.status_code == 200:
            text = response.json()["response"]
            suggestions = [
                line.strip()
                for line in text.strip().split("\n")
                if line.strip() and len(line.strip()) > 5
            ][:3]
            return suggestions
    except:
        pass

    return [
        "What are the eligibility criteria?",
        "How do I apply for this?",
        "Are there any exceptions?"
    ]


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        allowed = [".pdf", ".docx", ".xlsx",
                   ".csv", ".html", ".txt", ".md"]
        ext = os.path.splitext(file.filename)[1].lower()

        if ext not in allowed:
            return {
                "success": False,
                "message": f"File type {ext} not supported"
            }

        # Save file
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        print(f"\n Saved: {file.filename}")

        # Run ingestion directly
        print(" Running ingestion pipeline...")
        from src.ingestion.parsers.parser_router import load_documents
        from src.ingestion.chunker import chunk_documents
        from src.vectordb.chroma_manager import (
            store_chunks, clear_db, verify_db
        )

        clear_db()
        docs   = load_documents(UPLOAD_FOLDER)
        chunks = chunk_documents(docs)
        store_chunks(chunks)
        verify_db()
        clear_cache()

        print(f" Done: {len(chunks)} chunks stored")

        return {
            "success"        : True,
            "message"        : f"{file.filename} uploaded! {len(chunks)} chunks created.",
            "chunks_created" : len(chunks),
            "total_documents": len(docs)
        }

    except Exception as e:
        print(f" Error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}


@app.get("/documents")
def list_documents():
    files = []
    for file in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, file)
        size = os.path.getsize(path)
        files.append({
            "name"   : file,
            "size_kb": round(size / 1024, 1)
        })
    return {"documents": files}


@app.delete("/documents/{filename}")
def delete_document(filename: str):
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(file_path):
            return {"success": False, "message": "File not found"}

        os.remove(file_path)

        from src.ingestion.parsers.parser_router import load_documents
        from src.ingestion.chunker import chunk_documents
        from src.vectordb.chroma_manager import (
            store_chunks, clear_db
        )

        clear_db()
        docs = load_documents(UPLOAD_FOLDER)
        if docs:
            chunks = chunk_documents(docs)
            store_chunks(chunks)
        clear_cache()

        return {
            "success": True,
            "message": f"{filename} deleted"
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/cache/stats")
def cache_stats():
    return get_cache_stats()


@app.delete("/cache/clear")
def clear_all_cache():
    clear_cache()
    return {"message": "Cache cleared"}