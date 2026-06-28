import hashlib
import json
import os
import shutil
import sys
import threading
import time

import requests
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


# ---------------------------------------------------------
# Project Path Setup
# ---------------------------------------------------------

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            ".."
        )
    )
)

from src.auth import (
    get_demo_users,
    get_current_owner,
    hash_token,
    slugify_owner,
    verify_login
)
from src.cache.redis_cache import (
    REDIS_AVAILABLE,
    cache_client,
    clear_cache,
    get_cache_stats,
    get_cached_answer,
    set_cached_answer
)
from src.config_loader import load_config
from src.jobs import (
    create_job,
    get_job,
    latest_job,
    run_background_job,
    update_job
)
from src.retrieval.evidence import is_evidence_supported
from src.retrieval.generator import generate_answer
from src.retrieval.retriever import retrieve


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

config = load_config()

# Handles both:
# http://localhost:11434
# http://localhost:11434/api/generate
OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434"
).rstrip("/")

if OLLAMA_BASE_URL.endswith("/api/generate"):
    OLLAMA_BASE_URL = OLLAMA_BASE_URL.removesuffix(
        "/api/generate"
    )

if OLLAMA_BASE_URL.endswith("/api"):
    OLLAMA_BASE_URL = OLLAMA_BASE_URL.removesuffix(
        "/api"
    )

OLLAMA_GENERATE_URL = (
    f"{OLLAMA_BASE_URL}/api/generate"
)

OLLAMA_TAGS_URL = (
    f"{OLLAMA_BASE_URL}/api/tags"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    config.get("generation", {}).get("answer_model", "qwen2.5:7b")
)

OLLAMA_SUGGESTION_MODEL = os.getenv(
    "OLLAMA_SUGGESTION_MODEL",
    config.get("generation", {}).get(
        "suggestion_model",
        "qwen2.5:7b"
    )
)

UPLOAD_FOLDER = "documents"

RETRIEVAL_CONFIG = config.get("retrieval", {})

TOP_K = RETRIEVAL_CONFIG.get("top_k", 5)
MAX_DISTANCE = RETRIEVAL_CONFIG.get("max_distance", 0.95)

CACHE_TTL = config["cache"].get(
    "ttl_seconds",
    3600
)

SUGGESTIONS_CACHE_KEY = "askpolicy:suggestions"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Prevents multiple browser requests from generating
# suggestions simultaneously.
SUGGESTIONS_LOCK = threading.Lock()


# ---------------------------------------------------------
# FastAPI Setup
# ---------------------------------------------------------

app = FastAPI(title="AskPolicy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.mount(
    "/static",
    StaticFiles(directory="templates"),
    name="static"
)


class QuestionRequest(BaseModel):
    question: str


class LoginRequest(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------
# Ollama Utilities
# ---------------------------------------------------------

def call_ollama(
    prompt: str,
    timeout: int = 45,
    model: str = OLLAMA_MODEL
) -> str:
    """
    Sends one prompt directly to Ollama.
    Used for suggestions and follow-up questions.
    """

    try:
        print(
            f"  Sending to Ollama: "
            f"{OLLAMA_GENERATE_URL}"
        )

        response = requests.post(
            OLLAMA_GENERATE_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.85
                }
            },
            timeout=timeout
        )

        if response.status_code == 200:
            return response.json().get(
                "response",
                ""
            ).strip()

        print(
            f"  Ollama returned status code: "
            f"{response.status_code}"
        )

        print(
            f"  Ollama response: "
            f"{response.text[:300]}"
        )

        return ""

    except requests.exceptions.Timeout:
        print("  Ollama request timed out")
        return ""

    except Exception as error:
        print(f"  Ollama error: {error}")
        return ""


def is_ollama_available() -> bool:
    """
    Checks whether Ollama server is reachable.
    """

    try:
        response = requests.get(
            OLLAMA_TAGS_URL,
            timeout=5
        )

        return response.status_code == 200

    except Exception as error:
        print(
            f"  Ollama availability check failed: "
            f"{error}"
        )

        return False


def owner_folder(owner: str) -> str:
    if owner == "default":
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        return UPLOAD_FOLDER

    path = os.path.join(
        UPLOAD_FOLDER,
        slugify_owner(owner)
    )
    os.makedirs(path, exist_ok=True)
    return path


def safe_filename(filename: str) -> str:
    cleaned = os.path.basename(filename or "").strip()

    if not cleaned:
        raise ValueError("Filename is required.")

    return cleaned


# ---------------------------------------------------------
# Redis Cache Utilities
# ---------------------------------------------------------

def followup_cache_key(question: str) -> str:
    """
    Creates one cache key for a question's follow-up.
    """

    question_hash = hashlib.md5(
        question.strip()
        .lower()
        .encode("utf-8")
    ).hexdigest()

    return f"askpolicy:followup:{question_hash}"


def scoped_question(owner: str, question: str) -> str:
    return f"[owner:{owner}] {question}"


def get_cached_followup(question: str):
    """
    Gets saved follow-up question from Redis.
    """

    if not REDIS_AVAILABLE:
        return None

    try:
        value = cache_client.get(
            followup_cache_key(question)
        )

        if not value:
            return None

        if isinstance(value, bytes):
            value = value.decode("utf-8")

        return value

    except Exception as error:
        print(
            f"  Follow-up cache read failed: "
            f"{error}"
        )

        return None


def set_cached_followup(
    question: str,
    followup: str
):
    """
    Saves follow-up question in Redis.
    """

    if not REDIS_AVAILABLE or not followup:
        return

    try:
        cache_client.setex(
            followup_cache_key(question),
            CACHE_TTL,
            followup
        )

    except Exception as error:
        print(
            f"  Follow-up cache save failed: "
            f"{error}"
        )


def clear_suggestions_cache(owner: str | None = None):
    """
    Clears suggestions and all follow-up mappings.
    """

    if not REDIS_AVAILABLE:
        return

    try:
        cache_client.delete(SUGGESTIONS_CACHE_KEY)

        if owner:
            cache_client.delete(f"{SUGGESTIONS_CACHE_KEY}:{owner}")

        match = "askpolicy:followup:*"

        for key in cache_client.scan_iter(match=match):
            cache_client.delete(key)

        print(
            "  Cleared suggestions and follow-up cache"
        )

    except Exception as error:
        print(
            f"  Could not clear suggestion cache: "
            f"{error}"
        )


# ---------------------------------------------------------
# Answer Validation
# ---------------------------------------------------------

def is_grounded_answer(answer: str) -> bool:
    """
    Checks whether answer looks useful and document-grounded.
    """

    if not answer or not answer.strip():
        return False

    invalid_answers = [
        "i don't know based on provided documents",
        "i do not know based on provided documents",
        "cannot connect to ollama",
        "request timed out",
        "unexpected error",
        "error:",
        "no response"
    ]

    answer_lower = answer.lower()

    return not any(
        invalid_text in answer_lower
        for invalid_text in invalid_answers
    )


def get_relevant_chunks(
    question: str,
    owner: str = "default",
    allowed_sources=None
) -> list[dict]:
    """
    Retrieves relevant chunks from ChromaDB.
    """

    chunks = retrieve(
        question,
        top_k=TOP_K,
        owner=owner
    )

    if allowed_sources:
        chunks = [
            chunk
            for chunk in chunks
            if chunk["source"] in allowed_sources
        ]

    relevant_chunks = [
        chunk
        for chunk in chunks
        if chunk.get("distance", 999) <= MAX_DISTANCE
    ]

    return relevant_chunks


def text_chunks_to_context(
    texts: list[str],
    source: str
) -> list[dict]:
    """
    Converts plain chunk text into generator-compatible chunks.
    """

    return [
        {
            "text": text,
            "source": source,
            "distance": 0.0
        }
        for text in texts
        if text and text.strip()
    ]


# ---------------------------------------------------------
# ChromaDB Utilities
# ---------------------------------------------------------

def get_document_groups(owner: str = "default") -> dict:
    """
    Returns ChromaDB chunks grouped by source filename.
    """

    from src.vectordb.chroma_manager import get_collection

    collection = get_collection()

    if collection.count() == 0:
        return {}

    all_data = collection.get(where={"owner": owner})

    documents = all_data.get("documents", [])
    metadatas = all_data.get("metadatas", [])

    groups = {}

    for document, metadata in zip(documents, metadatas):
        source = (
            metadata.get("source", "unknown")
            if metadata
            else "unknown"
        )

        groups.setdefault(source, []).append(document)

    return groups


def get_corpus_signature(groups: dict) -> str:
    """
    Creates a signature of current documents and chunk counts.
    Used to reject old suggestion cache after upload/delete.
    """

    summary = sorted(
        [
            {
                "source": source,
                "chunk_count": len(chunks)
            }
            for source, chunks in groups.items()
        ],
        key=lambda item: item["source"]
    )

    raw = json.dumps(
        summary,
        sort_keys=True
    )

    return hashlib.md5(
        raw.encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------
# Follow-up Generation
# ---------------------------------------------------------

def generate_validated_followup(
    question: str,
    answer: str,
    chunks: list[dict],
    owner: str = "default"
):
    """
    Generates one document-grounded follow-up question.
    """

    cached_followup = get_cached_followup(
        scoped_question(owner, question)
    )

    if cached_followup:
        return cached_followup

    if not chunks:
        return None

    context = "\n\n".join(
        chunk["text"]
        for chunk in chunks[:3]
    )[:1800]

    if not context.strip():
        return None

    prompt = f"""Create exactly ONE factual follow-up question.

ORIGINAL QUESTION:
{question}

ORIGINAL ANSWER:
{answer}

DOCUMENT CONTENT:
{context}

RULES:
1. The follow-up must be answerable only from DOCUMENT CONTENT.
2. It must be related to the original answer.
3. Do not repeat the original question.
4. Do not ask opinion, vague, or inference questions.
5. Start exactly with:
Would you like to know more about
6. Maximum 15 words.
7. Return only one question.
"""

    followup = call_ollama(
        prompt,
        timeout=30
    )

    if not followup:
        return None

    followup = followup.split("\n")[0].strip()

    if not followup.lower().startswith(
        "would you like to know more about"
    ):
        return None

    # UI shows the friendly follow-up question.
    # Qwen receives a document-style question internally.
    document_question = followup.replace(
        "Would you like to know more about",
        "Explain"
    ).rstrip("?") + " based only on the provided document."

    followup_answer = generate_answer(
        document_question,
        chunks
    )

    if (
        not is_grounded_answer(followup_answer)
        or not is_evidence_supported(followup_answer, chunks)
    ):
        return None

    sources = sorted(
        list(
            set(
                chunk["source"]
                for chunk in chunks
            )
        )
    )

    # Cache using original wording because frontend sends this.
    set_cached_answer(
        scoped_question(owner, followup),
        followup_answer,
        sources
    )

    set_cached_followup(
        scoped_question(owner, question),
        followup
    )

    return followup


# ---------------------------------------------------------
# Suggestion Helpers
# ---------------------------------------------------------

def clean_generated_question(text: str) -> str:
    """
    Cleans Qwen output into a single question.
    """

    if not text:
        return ""

    return (
        text
        .split("\n")[0]
        .strip()
        .lstrip("0123456789.-) \"'")
        .rstrip("\"'")
    )


def create_one_valid_suggestion(
    owner: str,
    source: str,
    selected_texts: list[str],
    existing_suggestions: list[str]
):
    """
    Creates one question from selected chunks and validates it.
    Returns question string or None.
    """

    context_chunks = text_chunks_to_context(
        selected_texts,
        source
    )

    context = "\n\n".join(
        chunk["text"]
        for chunk in context_chunks
    )[:1800]

    if len(context.strip()) < 50:
        print("     SKIPPED: context too short")
        return None

    prompt = f"""Create exactly ONE factual question from the document content.

DOCUMENT CONTENT:
{context}

STRICT RULES:
1. The answer must be explicitly present in DOCUMENT CONTENT.
2. Ask about a concrete fact, instruction, step, requirement, feature, tool, date, number, or definition.
3. Do not ask vague questions.
4. Do not use phrases such as "this content" or "in practice".
5. Maximum 14 words.
6. Return only one question ending with ?.
"""

    generated = call_ollama(
        prompt,
        timeout=30,
        model=OLLAMA_SUGGESTION_MODEL
    )

    question = clean_generated_question(generated)

    if not question:
        print(
            "     REJECTED: Ollama returned nothing"
        )
        return None

    print(f"     Generated: {question}")

    if len(question) < 6:
        print(
            "     REJECTED: question is too short"
        )
        return None

    if not question.endswith("?"):
        print(
            "     REJECTED: invalid question format"
        )
        return None

    if question in existing_suggestions:
        print(
            "     REJECTED: duplicate question"
        )
        return None

    answer = generate_answer(
        question,
        context_chunks
    )

    if not is_grounded_answer(answer):
        print(
            "     REJECTED: answer was not grounded"
        )
        return None

    if not is_evidence_supported(answer, context_chunks):
        print(
            "     REJECTED: answer lacked evidence overlap"
        )
        return None

    set_cached_answer(
        scoped_question(owner, question),
        answer,
        [source]
    )

    print(f"     VALID: [{source}] {question}")

    return question


# ---------------------------------------------------------
# Basic Routes
# ---------------------------------------------------------

@app.get("/")
def home():
    return {
        "status": "AskPolicy API running"
    }


@app.get("/chat")
def chat_ui():
    return FileResponse("templates/index.html")


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "embedding_model": config["embeddings"]["model"],
        "generator_model": OLLAMA_MODEL,
        "suggestion_model": OLLAMA_SUGGESTION_MODEL,
        "ollama_url": OLLAMA_GENERATE_URL,
        "max_distance": MAX_DISTANCE
    }


@app.post("/login")
def login(request: LoginRequest):
    owner = verify_login(
        request.username,
        request.password
    )

    if not owner:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    password = get_demo_users().get(owner, request.password)

    return {
        "user": owner,
        "token": hash_token(f"{owner}:{password}")
    }


# ---------------------------------------------------------
# Ask Question Route
# ---------------------------------------------------------

@app.post("/ask")
def ask_question(
    request: QuestionRequest,
    owner: str = Depends(get_current_owner)
):
    question = request.question.strip()

    print(f"\nQuestion: {question}")

    if not question:
        return {
            "answer": "Please enter a question.",
            "sources": [],
            "cached": False,
            "followup": None
        }

    cache_question = scoped_question(owner, question)
    cached = get_cached_answer(cache_question)

    if cached:
        print("  Returning cached answer")

        answer = cached["answer"]
        sources = cached["sources"]

        followup = get_cached_followup(cache_question)

        if not followup:
            chunks = get_relevant_chunks(
                question,
                owner=owner,
                allowed_sources=sources
            )

            if chunks:
                followup = generate_validated_followup(
                    question,
                    answer,
                    chunks,
                    owner=owner
                )

        return {
            "answer": answer,
            "sources": sources,
            "cached": True,
            "followup": followup
        }

    print("  Searching ChromaDB...")

    chunks = retrieve(
        question,
        top_k=TOP_K,
        owner=owner
    )

    relevant_chunks = [
        chunk
        for chunk in chunks
        if chunk.get("distance", 999) <= MAX_DISTANCE
    ]

    print(
        f"  {len(chunks)} chunks retrieved, "
        f"{len(relevant_chunks)} passed relevance filter"
    )

    for chunk in chunks:
        print(
            f"     distance="
            f"{chunk.get('distance', 999):.4f} "
            f"source={chunk['source']}"
        )

    if not relevant_chunks:
        return {
            "answer": (
                "I don't know based on provided documents"
            ),
            "sources": [],
            "cached": False,
            "followup": None
        }

    answer = generate_answer(
        question,
        relevant_chunks
    )

    if (
        not is_grounded_answer(answer)
        or not is_evidence_supported(answer, relevant_chunks)
    ):
        return {
            "answer": (
                "I don't know based on provided documents"
            ),
            "sources": [],
            "cached": False,
            "followup": None
        }

    sources = sorted(
        list(
            set(
                chunk["source"]
                for chunk in relevant_chunks
            )
        )
    )

    set_cached_answer(
        cache_question,
        answer,
        sources
    )

    followup = generate_validated_followup(
        question,
        answer,
        relevant_chunks,
        owner=owner
    )

    return {
        "answer": answer,
        "sources": sources,
        "cached": False,
        "followup": followup
    }


# ---------------------------------------------------------
# Suggestions Route
# ---------------------------------------------------------

@app.get("/suggestions")
def get_suggestions(
    owner: str = Depends(get_current_owner)
):
    """
    Creates five validated document-based suggestions.

    Initial distribution is fair, for example:
    Small PDF -> 3
    Large DOCX -> 2

    If small PDF can create only 2 valid unique questions,
    missing suggestion is generated from another document
    that has more available chunks.
    """

    with SUGGESTIONS_LOCK:

        groups = get_document_groups(owner)

        if not groups:
            print(
                "  No document chunks found in ChromaDB"
            )

            return {
                "suggestions": [],
                "source": "no_documents"
            }

        current_signature = get_corpus_signature(groups)

        # Return cache only if cache matches current documents.
        if REDIS_AVAILABLE:
            try:
                cached = cache_client.get(
                    f"{SUGGESTIONS_CACHE_KEY}:{owner}"
                )

                if cached:
                    if isinstance(cached, bytes):
                        cached = cached.decode("utf-8")

                    cached_data = json.loads(cached)

                    cached_suggestions = cached_data.get(
                        "suggestions",
                        []
                    )

                    cached_signature = cached_data.get(
                        "corpus_signature"
                    )

                    if (
                        cached_suggestions
                        and cached_signature == current_signature
                    ):
                        print(
                            "  Returning cached validated "
                            "suggestions"
                        )

                        return cached_data

                    print(
                        "  Ignoring stale or empty "
                        "suggestion cache"
                    )

                    cache_client.delete(
                        f"{SUGGESTIONS_CACHE_KEY}:{owner}"
                    )

            except Exception as error:
                print(
                    f"  Suggestion cache read failed: "
                    f"{error}"
                )

        if not is_ollama_available():
            return {
                "suggestions": [],
                "source": "ollama_unavailable"
            }

        total_suggestions = 5
        suggestions = []

        sources = list(groups.keys())

        print(
            f"\n  Found {len(sources)} document(s): "
            f"{sources}"
        )

        # -------------------------------------------------
        # First round: fair distribution
        # Example with 2 documents: 3 + 2 = 5
        # -------------------------------------------------

        base = total_suggestions // len(sources)
        remainder = total_suggestions % len(sources)

        distribution = {}

        for index, source in enumerate(sources):
            distribution[source] = base + (
                1 if index < remainder else 0
            )

        print(
            f"  Initial distribution plan: "
            f"{distribution}"
        )

        for source, needed_count in distribution.items():
            document_chunks = groups.get(source, [])

            print(
                f"\n  Creating suggestions for: "
                f"{source}"
            )

            print(
                f"  Available chunks: "
                f"{len(document_chunks)}"
            )

            if not document_chunks:
                continue

            created_for_source = 0
            attempt = 0
            max_attempts = max(
                needed_count * 8,
                len(document_chunks)
            )

            while (
                created_for_source < needed_count
                and attempt < max_attempts
                and len(suggestions) < total_suggestions
            ):
                attempt += 1

                # Uses a different chunk each attempt.
                start_index = (
                    attempt - 1
                ) % len(document_chunks)

                selected_texts = [
                    document_chunks[start_index]
                ]

                print(
                    f"  Attempt {attempt}: "
                    f"using chunk {start_index + 1}"
                )

                question = create_one_valid_suggestion(
                    owner,
                    source,
                    selected_texts,
                    suggestions
                )

                if question:
                    suggestions.append(question)
                    created_for_source += 1

        # -------------------------------------------------
        # Second round: fill missing suggestions dynamically
        # Prefer document with MORE chunks first.
        # -------------------------------------------------

        remaining_needed = (
            total_suggestions - len(suggestions)
        )

        if remaining_needed > 0:
            print(
                f"\n  Need {remaining_needed} more "
                f"suggestion(s)."
            )

            print(
                "  Filling from documents with more "
                "available content..."
            )

            fallback_sources = sorted(
                sources,
                key=lambda source: len(groups[source]),
                reverse=True
            )

            for source in fallback_sources:
                if len(suggestions) >= total_suggestions:
                    break

                document_chunks = groups.get(source, [])

                if not document_chunks:
                    continue

                print(
                    f"\n  Fallback suggestions from: "
                    f"{source}"
                )

                max_fallback_attempts = (
                    len(document_chunks) * 2
                )

                for attempt in range(
                    max_fallback_attempts
                ):
                    if len(suggestions) >= total_suggestions:
                        break

                    start_index = (
                        attempt % len(document_chunks)
                    )

                    selected_texts = [
                        document_chunks[start_index]
                    ]

                    print(
                        f"  Fallback attempt "
                        f"{attempt + 1}: "
                        f"using chunk {start_index + 1}"
                    )

                    question = create_one_valid_suggestion(
                        owner,
                        source,
                        selected_texts,
                        suggestions
                    )

                    if question:
                        suggestions.append(question)

                        print(
                            "     FALLBACK VALID: "
                            f"[{source}] {question}"
                        )

        # Prevent old suggestion cache if document set changed.
        latest_groups = get_document_groups(owner)
        latest_signature = get_corpus_signature(
            latest_groups
        )

        if latest_signature != current_signature:
            print(
                "  Documents changed during suggestion "
                "generation."
            )

            return {
                "suggestions": [],
                "source": "documents_changed"
            }

        result = {
            "suggestions": suggestions[:total_suggestions],
            "source": "validated_documents",
            "corpus_signature": current_signature
        }

        print(
            f"\n  Final valid suggestions: "
            f"{len(result['suggestions'])}"
        )

        # Never cache empty result.
        if result["suggestions"] and REDIS_AVAILABLE:
            try:
                cache_client.setex(
                    f"{SUGGESTIONS_CACHE_KEY}:{owner}",
                    CACHE_TTL,
                    json.dumps(result)
                )

                print(
                    "  Validated suggestions cached"
                )

            except Exception as error:
                print(
                    f"  Suggestion cache save failed: "
                    f"{error}"
                )

        else:
            print(
                "  Suggestions are empty, so nothing "
                "was cached"
            )

        return result


# ---------------------------------------------------------
# Follow-up Route
# ---------------------------------------------------------

@app.get("/followup")
def get_followup(
    question: str,
    answer: str,
    owner: str = Depends(get_current_owner)
):
    """
    Returns a cached or newly created follow-up.
    """

    cached_followup = get_cached_followup(
        scoped_question(owner, question)
    )

    if cached_followup:
        return {
            "followup": cached_followup
        }

    chunks = get_relevant_chunks(question, owner=owner)

    followup = generate_validated_followup(
        question,
        answer,
        chunks,
        owner=owner
    )

    return {
        "followup": followup
    }


# ---------------------------------------------------------
# Upload Route
# ---------------------------------------------------------

def discover_document_folders() -> list[tuple[str, str]]:
    folders = []

    if not os.path.isdir(UPLOAD_FOLDER):
        return folders

    root_has_files = any(
        os.path.isfile(os.path.join(UPLOAD_FOLDER, name))
        for name in os.listdir(UPLOAD_FOLDER)
    )

    if root_has_files:
        folders.append(("default", UPLOAD_FOLDER))

    for name in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, name)

        if os.path.isdir(path):
            folders.append((slugify_owner(name), path))

    return folders


def rebuild_all_documents(job_id: str | None = None):
    from src.ingestion.chunker import chunk_documents
    from src.ingestion.parsers.parser_router import load_documents
    from src.vectordb.chroma_manager import (
        clear_db,
        store_chunks,
        verify_db
    )

    if job_id:
        update_job(job_id, status="running", step="Parsing documents")

    all_docs = []

    for folder_owner, folder in discover_document_folders():
        all_docs.extend(load_documents(folder, owner=folder_owner))

    if job_id:
        update_job(
            job_id,
            step=f"Chunking {len(all_docs)} documents"
        )

    clear_db()

    if not all_docs:
        clear_cache()
        clear_suggestions_cache()
        return {"docs": 0, "chunks": 0}

    chunks = chunk_documents(all_docs)

    if job_id:
        update_job(
            job_id,
            step=f"Embedding {len(chunks)} chunks"
        )

    if chunks:
        store_chunks(chunks)
        verify_db()

    clear_cache()
    clear_suggestions_cache()

    return {"docs": len(all_docs), "chunks": len(chunks)}


def finish_rebuild_job(job_id: str, success_message: str):
    try:
        result = rebuild_all_documents(job_id)
        update_job(
            job_id,
            status="complete",
            success=True,
            step="Ready",
            message=(
                f"{success_message} "
                f"{result['chunks']} chunks indexed."
            ),
            result=result
        )

    except Exception as error:
        import traceback

        print(f"  Background processing error: {error}")
        traceback.print_exc()
        update_job(
            job_id,
            status="failed",
            success=False,
            step="Failed",
            message=str(error)
        )


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    owner: str = Depends(get_current_owner)
):
    """
    Saves uploaded document and rebuilds ChromaDB.
    """

    try:
        allowed_extensions = [
            ".pdf",
            ".docx",
            ".xlsx",
            ".xls",
            ".csv",
            ".html",
            ".htm",
            ".txt",
            ".md"
        ]

        extension = os.path.splitext(
            file.filename
        )[1].lower()

        if extension not in allowed_extensions:
            return {
                "success": False,
                "message": (
                    f"File type {extension} "
                    f"is not supported."
                )
            }

        filename = safe_filename(file.filename)

        file_path = os.path.join(
            owner_folder(owner),
            filename
        )

        with open(file_path, "wb") as output_file:
            shutil.copyfileobj(
                file.file,
                output_file
            )

        print(f"\n  Saved: {filename} for {owner}")

        job_id = create_job("upload", owner, filename)

        run_background_job(
            job_id,
            lambda running_job_id: finish_rebuild_job(
                running_job_id,
                f"{filename} uploaded successfully."
            )
        )

        return {
            "success": True,
            "message": (
                f"{filename} uploaded. Processing started."
            ),
            "job_id": job_id
        }

    except Exception as error:
        import traceback

        print(f"  Upload error: {error}")
        traceback.print_exc()

        return {
            "success": False,
            "message": f"Upload failed: {str(error)}"
        }


# ---------------------------------------------------------
# Document Routes
# ---------------------------------------------------------

@app.get("/documents")
def list_documents(owner: str = Depends(get_current_owner)):
    try:
        files = []

        folder = owner_folder(owner)

        for filename in os.listdir(folder):
            file_path = os.path.join(
                folder,
                filename
            )

            if os.path.isfile(file_path):
                size = os.path.getsize(file_path)

                files.append(
                    {
                        "name": filename,
                        "size_kb": round(
                            size / 1024,
                            1
                        )
                    }
                )

        return {
            "documents": files
        }

    except Exception as error:
        return {
            "documents": [],
            "error": str(error)
        }


@app.delete("/documents/{filename}")
def delete_document(
    filename: str,
    owner: str = Depends(get_current_owner)
):
    """
    Deletes one document and rebuilds database
    from remaining documents.
    """

    try:
        file_path = os.path.join(
            owner_folder(owner),
            safe_filename(filename)
        )

        if not os.path.exists(file_path):
            return {
                "success": False,
                "message": (
                    f"File {filename} not found."
                )
            }

        os.remove(file_path)

        print(f"\n  Deleted: {filename}")

        job_id = create_job("delete", owner, filename)

        run_background_job(
            job_id,
            lambda running_job_id: finish_rebuild_job(
                running_job_id,
                f"{filename} deleted."
            )
        )

        return {
            "success": True,
            "message": f"{filename} deleted. Reindexing started.",
            "job_id": job_id
        }

    except Exception as error:
        print(f"  Delete error: {error}")

        return {
            "success": False,
            "message": f"Delete failed: {str(error)}"
        }


@app.get("/jobs/latest")
def get_latest_processing_job(
    owner: str = Depends(get_current_owner)
):
    return {
        "job": latest_job(owner)
    }


@app.get("/jobs/{job_id}")
def get_processing_job(
    job_id: str,
    owner: str = Depends(get_current_owner)
):
    job = get_job(job_id, owner=owner)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


# ---------------------------------------------------------
# Cache Routes
# ---------------------------------------------------------

@app.get("/cache/stats")
def cache_stats():
    return get_cache_stats()


@app.delete("/cache/clear")
def clear_all_cache():
    clear_cache()
    clear_suggestions_cache()

    return {
        "message": (
            "Answer, suggestion, and follow-up cache "
            "cleared."
        )
    }


# ---------------------------------------------------------
# Debug Routes
# ---------------------------------------------------------

@app.get("/debug/sources")
def debug_sources(owner: str = Depends(get_current_owner)):
    groups = get_document_groups(owner)

    return {
        "total_documents": len(groups),
        "chunks_per_document": {
            source: len(chunks)
            for source, chunks in groups.items()
        }
    }


@app.get("/debug/suggestions")
def debug_suggestions(owner: str = Depends(get_current_owner)):
    if not REDIS_AVAILABLE:
        return {
            "redis_available": False,
            "cached_suggestions": None
        }

    try:
        cached = cache_client.get(
            f"{SUGGESTIONS_CACHE_KEY}:{owner}"
        )

        if not cached:
            return {
                "redis_available": True,
                "cached_suggestions": None
            }

        if isinstance(cached, bytes):
            cached = cached.decode("utf-8")

        return {
            "redis_available": True,
            "cached_suggestions": json.loads(cached)
        }

    except Exception as error:
        return {
            "redis_available": True,
            "error": str(error)
        }


@app.get("/debug/ollama")
def debug_ollama():
    available = is_ollama_available()

    if not available:
        return {
            "ollama_reachable": False
        }

    start_time = time.time()

    response = call_ollama(
        "Say hello in one word.",
        timeout=30
    )

    elapsed = time.time() - start_time

    return {
        "ollama_reachable": True,
        "model": OLLAMA_MODEL,
        "response": response,
        "elapsed_seconds": round(elapsed, 2)
    }
