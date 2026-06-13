import hashlib
import json
import redis
from src.config_loader import load_config
from sentence_transformers import SentenceTransformer

config     = load_config()
BATCH_SIZE = config["embeddings"]["batch_size"]  # 32
_model     = None

# ── Redis for embedding cache ─────────────────────────────────
try:
    cache = redis.Redis(
        host=config["cache"]["host"],
        port=config["cache"]["port"],
        db=2,  # separate db for embeddings
        decode_responses=False
    )
    cache.ping()
    CACHE_AVAILABLE = True
    print(" Embedding cache (Redis) connected")
except:
    CACHE_AVAILABLE = False
    print("Embedding cache not available")

EMBED_TTL = config["cache"]["embedding_ttl"]  # 24 hours


# ── Model loading (singleton) ─────────────────────────────────
def get_model():
    global _model
    if _model is None:
        model_name = config["embeddings"]["model"]
        print(f" Loading embedding model: {model_name}")
        _model = SentenceTransformer(model_name)
        print(f" Model loaded")
    return _model


# ── Single embedding with cache ───────────────────────────────
def get_embedding(text):
    # Check cache first
    if CACHE_AVAILABLE:
        cache_key = "emb:" + hashlib.md5(
            text.encode()
        ).hexdigest()
        cached = cache.get(cache_key)
        if cached:
            return json.loads(cached)

    # Generate embedding
    model     = get_model()
    embedding = model.encode(text).tolist()

    # Save to cache
    if CACHE_AVAILABLE:
        cache.setex(
            cache_key,
            EMBED_TTL,
            json.dumps(embedding)
        )

    return embedding


# ── BATCH embedding (much faster) ────────────────────────────
def get_embeddings_batch(texts):
    """
    Embed multiple texts at once
    Much faster than one by one

    Example:
    One by one: 80 chunks × 0.1s = 8 seconds
    Batch of 32: 3 batches × 0.3s = 0.9 seconds
    """
    all_embeddings = []
    uncached_texts = []
    uncached_idx   = []

    # Step 1: Check cache for each text
    for i, text in enumerate(texts):
        if CACHE_AVAILABLE:
            cache_key = "emb:" + hashlib.md5(
                text.encode()
            ).hexdigest()
            cached = cache.get(cache_key)
            if cached:
                all_embeddings.append(
                    (i, json.loads(cached))
                )
                continue

        uncached_texts.append(text)
        uncached_idx.append(i)

    print(f"  Cache hits: {len(all_embeddings)}, "
          f"To embed: {len(uncached_texts)}")

    # Step 2: Batch embed uncached texts
    if uncached_texts:
        model = get_model()

        # Process in batches of BATCH_SIZE
        for batch_start in range(
            0, len(uncached_texts), BATCH_SIZE
        ):
            batch_end   = batch_start + BATCH_SIZE
            batch_texts = uncached_texts[batch_start:batch_end]

            print(f"  Embedding batch "
                  f"{batch_start//BATCH_SIZE + 1}/"
                  f"{(len(uncached_texts)-1)//BATCH_SIZE + 1} "
                  f"({len(batch_texts)} texts)...")

            # Encode entire batch at once
            batch_embeddings = model.encode(
                batch_texts,
                batch_size=BATCH_SIZE,
                show_progress_bar=False
            ).tolist()

            # Save each to cache + results
            for j, embedding in enumerate(batch_embeddings):
                orig_idx = uncached_idx[batch_start + j]
                all_embeddings.append((orig_idx, embedding))

                # Cache it
                if CACHE_AVAILABLE:
                    text      = uncached_texts[batch_start + j]
                    cache_key = "emb:" + hashlib.md5(
                        text.encode()
                    ).hexdigest()
                    cache.setex(
                        cache_key,
                        EMBED_TTL,
                        json.dumps(embedding)
                    )

    # Step 3: Sort by original index
    all_embeddings.sort(key=lambda x: x[0])
    return [emb for _, emb in all_embeddings]