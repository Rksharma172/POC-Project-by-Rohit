import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
))

import shutil
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

# ── Upload Folder ─────────────────────────────────────────────
UPLOAD_FOLDER = "documents"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ── Request Models ────────────────────────────────────────────
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
    print(f"\n Question: {request.question}")

    # Step 1: Check Redis cache first
    cached = get_cached_answer(request.question)
    if cached:
        print(" Returning cached answer")
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

    # Step 2: Retrieve relevant chunks from ChromaDB
    print(" Searching ChromaDB...")
    chunks = retrieve(request.question, top_k=5)

    if not chunks:
        return {
            "answer"     : "I could not find relevant information in the uploaded documents. Please make sure you have uploaded the correct policy documents.",
            "sources"    : [],
            "cached"     : False,
            "suggestions": []
        }

    # Step 3: Generate answer using Qwen
    print(" Generating answer...")
    answer  = generate_answer(request.question, chunks)
    sources = list(set(c["source"] for c in chunks))

    # Step 4: Generate follow-up suggestions
    suggestions = generate_followups(request.question, answer)

    # Step 5: Save to Redis cache
    set_cached_answer(request.question, answer, sources)

    return {
        "answer"     : answer,
        "sources"    : sources,
        "cached"     : False,
        "suggestions": suggestions
    }


def generate_followups(question, answer):
    """
    Generate 3 follow-up question suggestions
    based on current question and answer
    """
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

Question: {question}
Answer: {answer[:300]}

Rules:
- Each question must be max 10 words
- Must be relevant to the topic
- Return ONLY 3 questions one per line
- No numbering, no bullets, no extra text"""

        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model" : ollama_model,
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

    except Exception as e:
        print(f" Follow-up generation failed: {e}")

    # Default suggestions if Qwen fails
    return [
        "What are the eligibility criteria?",
        "How do I apply for this?",
        "Are there any exceptions to this policy?"
    ]


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a document and re-run ingestion pipeline
    """
    try:
        # Step 1: Check file type
        allowed = [".pdf", ".docx", ".xlsx",
                   ".csv", ".html", ".txt", ".md"]
        ext = os.path.splitext(file.filename)[1].lower()

        if ext not in allowed:
            return {
                "success": False,
                "message": f"File type {ext} not supported. Allowed: {allowed}"
            }

        # Step 2: Save file to documents folder
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        print(f"\n File saved: {file.filename}")

        # Step 3: Show all files in folder
        all_files = os.listdir(UPLOAD_FOLDER)
        print(f" All files: {all_files}")

        # Step 4: Clear old ChromaDB data
        print(" Clearing old ChromaDB...")
        from src.vectordb.chroma_manager import (
            clear_db,
            store_chunks,
            verify_db
        )
        clear_db()

        # Step 5: Parse all documents fresh
        print(" Parsing all documents...")
        from src.ingestion.parsers.parser_router import load_documents
        from src.ingestion.chunker import chunk_documents

        docs = load_documents(UPLOAD_FOLDER)
        print(f" Loaded {len(docs)} documents")

        if not docs:
            return {
                "success": False,
                "message": "No documents could be parsed. Please check the file."
            }

        # Step 6: Chunk all documents
        print(" Chunking documents...")
        chunks = chunk_documents(docs)
        print(f" Created {len(chunks)} chunks")

        # Step 7: Store all chunks in ChromaDB
        print(" Storing in ChromaDB...")
        store_chunks(chunks)

        # Step 8: Verify storage
        verify_db()

        # Step 9: Clear answer cache
        clear_cache()
        print(" Cache cleared")

        return {
            "success"        : True,
            "message"        : f"{file.filename} uploaded successfully! {len(chunks)} chunks created from {len(docs)} documents.",
            "chunks_created" : len(chunks),
            "total_documents": len(docs),
            "all_files"      : all_files
        }

    except Exception as e:
        print(f" Upload error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Upload failed: {str(e)}"
        }


@app.get("/documents")
def list_documents():
    """
    List all uploaded documents
    """
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
    """
    Delete a document and re-run ingestion
    """
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        if not os.path.exists(file_path):
            return {
                "success": False,
                "message": f"File {filename} not found"
            }

        # Delete the file
        os.remove(file_path)
        print(f"\n Deleted: {filename}")

        # Re-run ingestion with remaining files
        from src.ingestion.parsers.parser_router import load_documents
        from src.ingestion.chunker import chunk_documents
        from src.vectordb.chroma_manager import (
            store_chunks,
            clear_db
        )

        clear_db()
        docs = load_documents(UPLOAD_FOLDER)

        if docs:
            chunks = chunk_documents(docs)
            store_chunks(chunks)
            print(f" Re-ingested {len(chunks)} chunks")
        else:
            print(" No documents remaining")

        # Clear cache
        clear_cache()

        return {
            "success": True,
            "message": f"{filename} deleted successfully"
        }

    except Exception as e:
        print(f" Delete error: {e}")
        return {
            "success": False,
            "message": f"Delete failed: {str(e)}"
        }


@app.get("/cache/stats")
def cache_stats():
    """
    Get Redis cache statistics
    Shown in frontend sidebar
    """
    return get_cache_stats()


@app.delete("/cache/clear")
def clear_all_cache():
    """
    Manually clear all cached answers
    """
    clear_cache()
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
