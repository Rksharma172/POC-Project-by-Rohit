import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
))

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
    get_cached_answer,
    set_cached_answer,
    clear_cache,
    get_cache_stats
)

# ── Constants ─────────────────────────────────────────────────
OLLAMA_HOST  = os.getenv(
    "OLLAMA_URL",
    "http://host.docker.internal:11434"
)
OLLAMA_MODEL = "qwen2.5:3b"          # ← 3b model
UPLOAD_FOLDER = "documents"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Create FastAPI app ────────────────────────────────────────
app = FastAPI(title="AskPolicy API")

# ── CORS Middleware ───────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ── Serve Static Files (CSS + JS) ────────────────────────────
app.mount(
    "/static",
    StaticFiles(directory="templates"),
    name="static"
)


# ── Request Models ────────────────────────────────────────────
class QuestionRequest(BaseModel):
    question: str


# ── Helper: Call Ollama ───────────────────────────────────────
def call_ollama(prompt: str, timeout: int = 60) -> str:
    """
    Single function to call Ollama
    Used by all endpoints that need Qwen
    """
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model" : OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "top_p"      : 0.9
                }
            },
            timeout=timeout
        )
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        return ""
    except Exception as e:
        print(f"   Ollama error: {e}")
        return ""


# ── Routes ───────────────────────────────────────────────────

@app.get("/")
def home():
    return {"status": "AskPolicy API running "}


@app.get("/chat")
def chat_ui():
    return FileResponse("templates/index.html")


@app.get("/health")
def health_check():
    return {
        "status" : "healthy",
        "api"    : "running",
        "model"  : OLLAMA_MODEL,
        "version": "1.0.0"
    }


@app.post("/ask")
def ask_question(request: QuestionRequest):
    print(f"\n Question: {request.question}")

    # Step 1: Check Redis cache first
    cached = get_cached_answer(request.question)
    if cached:
        print("   Returning cached answer")
        followup = get_single_followup(
            request.question,
            cached["answer"]
        )
        return {
            "answer" : cached["answer"],
            "sources": cached["sources"],
            "cached" : True,
            "followup": followup
        }

    # Step 2: Retrieve relevant chunks
    print("   Searching ChromaDB...")
    chunks = retrieve(request.question, top_k=5)

    if not chunks:
        return {
            "answer"  : "I could not find relevant information in the uploaded documents. Please make sure you have uploaded the correct policy documents.",
            "sources" : [],
            "cached"  : False,
            "followup": None
        }

    # Step 3: Generate answer
    print("   Generating answer with Qwen 2.5:3b...")
    answer  = generate_answer(request.question, chunks)
    sources = list(set(c["source"] for c in chunks))

    # Step 4: Generate 1 follow-up
    followup = get_single_followup(request.question, answer)

    # Step 5: Cache answer
    set_cached_answer(request.question, answer, sources)

    return {
        "answer"  : answer,
        "sources" : sources,
        "cached"  : False,
        "followup": followup
    }


def get_single_followup(question: str, answer: str) -> str:
    """
    Generate 1 relevant follow-up suggestion
    Starts with "Would you like to know more about..."
    """
<<<<<<< HEAD
    prompt = f"""Based on this Q&A about company policy,
generate exactly ONE follow-up question starting with
"Would you like to know more about"
=======
    import requests
    import os

    ollama_host = os.getenv(
        "OLLAMA_URL",
        "http://host.docker.internal:11434"
    )
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

    try:
        prompt = f"""Based on this Q&A about company policies,
suggest exactly 3 short follow-up questions an employee might ask.
>>>>>>> a190bc1159827cff98ebb88516f77223772f2a4e

Question: {question}
Answer: {answer[:200]}

Rules:
- Must start with "Would you like to know more about"
- Must be relevant to the topic
- Max 15 words total
- Return ONLY the question nothing else"""

<<<<<<< HEAD
    result = call_ollama(prompt, timeout=30)
=======
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model" : ollama_model,
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )
>>>>>>> a190bc1159827cff98ebb88516f77223772f2a4e

    if result and "would you like" in result.lower():
        # Take only first line
        lines = [
            l.strip() for l in result.split("\n")
            if l.strip() and len(l.strip()) > 5
        ]
        if lines:
            return lines[0]

    # Default fallback
    topic = question.lower()\
        .replace("what is", "")\
        .replace("what are", "")\
        .replace("how do i", "")\
        .replace("how", "")\
        .strip()
    return f"Would you like to know more about {topic}?"


@app.get("/suggestions")
def get_suggestions():
    """
    Generate 1 suggestion per document
    Max 5 suggestions total
    Always shown in UI — never hidden
    """
    try:
        from src.vectordb.chroma_manager import get_collection
        col   = get_collection()
        count = col.count()

        if count == 0:
            return {"suggestions": get_default_suggestions()}

        # Get all chunks with metadata
        all_data = col.get()
        docs     = all_data.get("documents",  [])
        metas    = all_data.get("metadatas",  [])

        if not docs:
            return {"suggestions": get_default_suggestions()}

        # Group chunks by source document
        doc_chunks = {}
        for doc, meta in zip(docs, metas):
            source = meta.get("source", "unknown")
            if source not in doc_chunks:
                doc_chunks[source] = []
            if len(doc_chunks[source]) < 3:
                doc_chunks[source].append(doc)

        print(f"  📂 Generating suggestions for {len(doc_chunks)} documents")

        suggestions = []

        # Generate 1 suggestion per document
        for source, chunks in list(doc_chunks.items())[:5]:
            sample_text = "\n".join(chunks[:2])[:500]

            prompt = f"""Based on this content from document "{source}",
generate exactly ONE short question an employee would ask.

CONTENT:
{sample_text}

Rules:
- Max 10 words
- Must be answerable from content
- Return ONLY the question
- No numbering, no bullets"""

            result = call_ollama(prompt, timeout=30)

            if result:
                question = result.strip().split("\n")[0].strip()
                if len(question) > 5 and "?" in question:
                    suggestions.append(question)
                    print(f"  ✅ Suggestion for {source}: {question}")

        if len(suggestions) >= 1:
            return {"suggestions": suggestions}

    except Exception as e:
        print(f"  ⚠️ Suggestion generation failed: {e}")

    return {"suggestions": get_default_suggestions()}

def get_default_suggestions():
    """Default suggestions when no documents uploaded"""
    return [
        "What is the annual leave policy?",
        "What are the travel expense limits?",
        "What is the work from home policy?",
        "What are the office timings?",
        "How do I apply for sick leave?"
    ]


@app.get("/followup")
def get_followup(question: str, answer: str):
    """
    Generate 1 follow-up suggestion
    Called from frontend after every answer
    """
    followup = get_single_followup(question, answer)
    return {"followup": followup}


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload document and re-run ingestion pipeline
    """
    try:
        # Check file type
        allowed = [".pdf", ".docx", ".xlsx",
                   ".csv", ".html", ".txt", ".md"]
        ext = os.path.splitext(file.filename)[1].lower()

        if ext not in allowed:
            return {
                "success": False,
                "message": f"File type {ext} not supported. Allowed: {allowed}"
            }

        # Save file
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        print(f"\n  Saved: {file.filename}")

        all_files = os.listdir(UPLOAD_FOLDER)
        print(f"  All files: {all_files}")

        # Clear old ChromaDB
        print("  Clearing old ChromaDB...")
        from src.vectordb.chroma_manager import (
            clear_db, store_chunks, verify_db
        )
        clear_db()

        # Parse all documents
        print("  Parsing documents...")
        from src.ingestion.parsers.parser_router import load_documents
        from src.ingestion.chunker import chunk_documents

        docs = load_documents(UPLOAD_FOLDER)
        print(f"  Loaded {len(docs)} documents")

        if not docs:
            return {
                "success": False,
                "message": "No documents could be parsed."
            }

        # Chunk
        print("  Chunking...")
        chunks = chunk_documents(docs)
        print(f"  Created {len(chunks)} chunks")

        # Store
        print("  Storing in ChromaDB...")
        store_chunks(chunks)
        verify_db()

        # Clear cache
        clear_cache()
        print("  Cache cleared")

        return {
            "success"        : True,
            "message"        : f" {file.filename} uploaded! {len(chunks)} chunks from {len(docs)} documents.",
            "chunks_created" : len(chunks),
            "total_documents": len(docs),
            "all_files"      : all_files
        }

    except Exception as e:
        print(f"  Upload error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Upload failed: {str(e)}"
        }


@app.get("/documents")
def list_documents():
    """List all uploaded documents"""
    try:
        files = []
        for file in os.listdir(UPLOAD_FOLDER):
            path = os.path.join(UPLOAD_FOLDER, file)
            if os.path.isfile(path):
                size = os.path.getsize(path)
                files.append({
                    "name"   : file,
                    "size_kb": round(size / 1024, 1)
                })
        return {"documents": files}
    except Exception as e:
        return {"documents": [], "error": str(e)}


@app.delete("/documents/{filename}")
def delete_document(filename: str):
    """Delete a document and re-run ingestion"""
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        if not os.path.exists(file_path):
            return {
                "success": False,
                "message": f"File {filename} not found"
            }

        os.remove(file_path)
        print(f"\n Deleted: {filename}")

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
            print(f"  Re-ingested {len(chunks)} chunks")
        else:
            print("  No documents remaining")

        clear_cache()

        return {
            "success": True,
            "message": f" {filename} deleted"
        }

    except Exception as e:
        print(f"  Delete error: {e}")
        return {
            "success": False,
            "message": f"Delete failed: {str(e)}"
        }


@app.get("/cache/stats")
def cache_stats():
    return get_cache_stats()


@app.delete("/cache/clear")
def clear_all_cache():
    clear_cache()
<<<<<<< HEAD
    return {"message": " Cache cleared"}
=======
    return {"message": "Cache cleared successfully"}


@app.get("/health")
def health_check():
    """
    Health check endpoint
    Used by Docker to verify API is running
    """
    return {
        "status" : "healthy",
        "api"    : "running",
        "version": "1.0.0"
    }
>>>>>>> a190bc1159827cff98ebb88516f77223772f2a4e
