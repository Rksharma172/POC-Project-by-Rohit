import redis
import json
import hashlib
from src.config_loader import load_config

config = load_config()

try:
    cache_client = redis.Redis(
        host=config["cache"]["host"],
        port=config["cache"]["port"],
        db=0,
        decode_responses=True
    )
    cache_client.ping()
    REDIS_AVAILABLE = True
    print("Redis connected successfully")

except Exception as e:
    print(f"Redis not available: {e}")
    REDIS_AVAILABLE = False

CACHE_TTL = config["cache"]["ttl_seconds"]


def make_cache_key(question: str) -> str:
    return "askpolicy:" + hashlib.md5(question.lower().strip().encode()).hexdigest()


def get_cached_answer(question: str):
    if not REDIS_AVAILABLE:
        return None
    try:
        key    = make_cache_key(question)
        cached = cache_client.get(key)
        if cached:
            print(f"Cache HIT: {question[:50]}...")
            return json.loads(cached)
        print(f"Cache MISS: {question[:50]}...")
        return None
    except Exception as e:
        print(f"Cache get error: {e}")
        return None


def set_cached_answer(question: str, answer: str, sources: list):
    if not REDIS_AVAILABLE:
        return
    try:
        key   = make_cache_key(question)
        value = json.dumps({"answer": answer, "sources": sources, "cached": True})
        cache_client.setex(key, CACHE_TTL, value)
        print(f"Answer cached: {question[:50]}...")
    except Exception as e:
        print(f"Cache set error: {e}")


def clear_cache():
    if not REDIS_AVAILABLE:
        return
    try:
        keys = cache_client.keys("askpolicy:*")
        if keys:
            cache_client.delete(*keys)
            print(f"Cleared {len(keys)} cached answers")
        else:
            print("No cached answers to clear")
    except Exception as e:
        print(f"Cache clear error: {e}")


def get_cache_stats():
    if not REDIS_AVAILABLE:
        return {"status": "Redis not available", "cached_answers": 0, "ttl_seconds": 0}
    try:
        keys = cache_client.keys("askpolicy:*")
        return {"status": "connected", "cached_answers": len(keys), "ttl_seconds": CACHE_TTL}
    except Exception as e:
        return {"status": f"error: {e}", "cached_answers": 0, "ttl_seconds": 0}