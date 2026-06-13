import redis
import json
import hashlib
from src.config_loader import load_config

config = load_config()

# ── Connect to Redis ──────────────────────────────────────────
try:
    cache_client = redis.Redis(
        host=config["cache"]["host"],        # localhost
        port=config["cache"]["port"],        # 6379
        db=0,                                # database 0
        decode_responses=True                # return strings
    )
    cache_client.ping()                      # test connection
    REDIS_AVAILABLE = True
    print(" Redis connected successfully")

except Exception as e:
    print(f" Redis not available: {e}")
    print("   Running without cache")
    REDIS_AVAILABLE = False

CACHE_TTL = config["cache"]["ttl_seconds"]  # 1 hour


# ── Helper: Convert question to cache key ─────────────────────
def make_cache_key(question: str) -> str:
    """
    Converts question text to a short unique key

    Example:
    "What is the leave policy?"
    → "askpolicy:a1b2c3d4e5f6..."

    Why MD5 hash?
    → always same length
    → no special characters
    → unique for each question
    """
    return "askpolicy:" + hashlib.md5(
        question.lower().strip().encode()
    ).hexdigest()


# ── Get answer from cache ─────────────────────────────────────
def get_cached_answer(question: str):
    """
    Check if we already answered this question before

    Returns:
    → dict with answer + sources  if found  (cache HIT)
    → None                        if not found (cache MISS)

    Real example:
    Employee asks "What is leave policy?" 2nd time
    → cache HIT → return instantly 
    → no need to call ChromaDB or Qwen again
    """
    if not REDIS_AVAILABLE:
        return None

    try:
        key    = make_cache_key(question)
        cached = cache_client.get(key)

        if cached:
            print(f" Cache HIT: {question[:50]}...")
            return json.loads(cached)   # string → dict

        print(f" Cache MISS: {question[:50]}...")
        return None

    except Exception as e:
        print(f" Cache get error: {e}")
        return None


# ── Save answer to cache ──────────────────────────────────────
def set_cached_answer(question: str, answer: str, sources: list):
    """
    Save answer to Redis so next time
    same question returns instantly

    Automatically expires after TTL (1 hour)
    So stale answers don't stay forever

    Real example:
    Employee asks "What is leave policy?"
    → RAG runs → gets answer
    → we save answer to Redis
    → next time same question → instant ⚡
    """
    if not REDIS_AVAILABLE:
        return

    try:
        key   = make_cache_key(question)
        value = json.dumps({               # dict → string
            "answer" : answer,
            "sources": sources,
            "cached" : True
        })

        # setex = set with expiry
        # after TTL seconds Redis deletes it automatically
        cache_client.setex(key, CACHE_TTL, value)
        print(f" Answer cached: {question[:50]}...")

    except Exception as e:
        print(f" Cache set error: {e}")


# ── Clear all cached answers ──────────────────────────────────
def clear_cache():
    """
    Delete all cached answers

    When to use:
    → New document uploaded
    → Old answers might be wrong now
    → Need fresh answers from new docs

    Real example:
    You upload new leave policy PDF
    → old cached answers about leave are wrong
    → clear cache → fresh answers generated
    """
    if not REDIS_AVAILABLE:
        return

    try:
        # Find all keys that start with "askpolicy:"
        keys = cache_client.keys("askpolicy:*")

        if keys:
            cache_client.delete(*keys)    # delete all at once
            print(f" Cleared {len(keys)} cached answers")
        else:
            print(" No cached answers to clear")

    except Exception as e:
        print(f" Cache clear error: {e}")


# ── Get cache statistics ──────────────────────────────────────
def get_cache_stats():
    """
    Returns info about current cache state

    Used by:
    → api.py GET /cache/stats endpoint
    → frontend shows live cache stats

    Returns:
    {
        "status": "connected",
        "cached_answers": 5,
        "ttl_seconds": 3600
    }
    """
    if not REDIS_AVAILABLE:
        return {
            "status"         : "Redis not available",
            "cached_answers" : 0,
            "ttl_seconds"    : 0
        }

    try:
        keys = cache_client.keys("askpolicy:*")
        return {
            "status"         : "connected",
            "cached_answers" : len(keys),
            "ttl_seconds"    : CACHE_TTL
        }

    except Exception as e:
        return {
            "status"         : f"error: {e}",
            "cached_answers" : 0,
            "ttl_seconds"    : 0
        }