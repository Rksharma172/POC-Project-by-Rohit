import hashlib
import json
import redis
from src.config_loader import load_config
from sentence_transformers import SentenceTransformer

config     = load_config()
BATCH_SIZE = config["embeddings"]["batch_size"]
_model     = None

try:
    cache = redis.Redis(
        host=config["cache"]["host"],
        port=config["cache"]["port"],
        db=2,
        decode_responses=False
    )
    cache.ping()
    CACHE_AVAILABLE = True
    print("Embedding cache (Redis) connected")
except:
    CACHE_AVAILABLE = False
    print("Embedding cache not available")

EMBED_TTL = config["cache"]["embedding_ttl"]


def get_model():
    global _model
    if _model is None:
        model_name = config["embeddings"]["model"]
        print(f"Loading embedding model: {model_name}")
        _model = SentenceTransformer(model_name)
        print(f"Model loaded")
    return _model


def get_embedding(text):
    if CACHE_AVAILABLE:
        cache_key = "emb:" + hashlib.md5(text.encode()).hexdigest()
        cached = cache.get(cache_key)
        if cached:
            return json.loads(cached)

    model     = get_model()
    embedding = model.encode(text).tolist()

    if CACHE_AVAILABLE:
        cache.setex(cache_key, EMBED_TTL, json.dumps(embedding))

    return embedding


def get_embeddings_batch(texts):
    all_embeddings = []
    uncached_texts = []
    uncached_idx   = []

    for i, text in enumerate(texts):
        if CACHE_AVAILABLE:
            cache_key = "emb:" + hashlib.md5(text.encode()).hexdigest()
            cached = cache.get(cache_key)
            if cached:
                all_embeddings.append((i, json.loads(cached)))
                continue

        uncached_texts.append(text)
        uncached_idx.append(i)

    print(f"  Cache hits: {len(all_embeddings)}, To embed: {len(uncached_texts)}")

    if uncached_texts:
        model = get_model()

        for batch_start in range(0, len(uncached_texts), BATCH_SIZE):
            batch_end   = batch_start + BATCH_SIZE
            batch_texts = uncached_texts[batch_start:batch_end]

            print(f"  Embedding batch {batch_start//BATCH_SIZE + 1}/"
                  f"{(len(uncached_texts)-1)//BATCH_SIZE + 1} ({len(batch_texts)} texts)...")

            batch_embeddings = model.encode(
                batch_texts, batch_size=BATCH_SIZE, show_progress_bar=False
            ).tolist()

            for j, embedding in enumerate(batch_embeddings):
                orig_idx = uncached_idx[batch_start + j]
                all_embeddings.append((orig_idx, embedding))

                if CACHE_AVAILABLE:
                    text      = uncached_texts[batch_start + j]
                    cache_key = "emb:" + hashlib.md5(text.encode()).hexdigest()
                    cache.setex(cache_key, EMBED_TTL, json.dumps(embedding))

    all_embeddings.sort(key=lambda x: x[0])
    return [emb for _, emb in all_embeddings]