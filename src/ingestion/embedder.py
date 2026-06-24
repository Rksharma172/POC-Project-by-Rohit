import hashlib
import json

import redis
from sentence_transformers import SentenceTransformer

from src.config_loader import load_config


config = load_config()

BATCH_SIZE = config["embeddings"]["batch_size"]
EMBED_TTL = config["cache"]["embedding_ttl"]

_model = None


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

except Exception:
    CACHE_AVAILABLE = False
    print("Embedding cache not available")


def get_model():
    """
    Load the BGE model only once and reuse it for:
    - document chunk embeddings
    - sentence embeddings during semantic chunking
    - user-question embeddings during retrieval
    """
    global _model

    if _model is None:
        model_name = config["embeddings"]["model"]

        print(f"Loading embedding model: {model_name}")

        _model = SentenceTransformer(model_name)

        print("Embedding model loaded")

    return _model


def _cache_key(text: str) -> str:
    """
    Create a short, stable Redis key for one text input.
    """
    text_hash = hashlib.md5(
        text.encode("utf-8")
    ).hexdigest()

    return f"emb:{text_hash}"


def get_embedding(text: str) -> list[float]:
    """
    Create one normalized BGE embedding.

    Normalization is important because it makes the vector
    comparison consistent for Chroma cosine search and sentence similarity.
    """
    if not text or not text.strip():
        return []

    key = _cache_key(text)

    # 1. Use cached embedding if it already exists.
    if CACHE_AVAILABLE:
        cached = cache.get(key)

        if cached:
            return json.loads(cached)

    # 2. Otherwise generate embedding using BGE.
    model = get_model()

    embedding = model.encode(
        text,
        normalize_embeddings=True
    ).tolist()

    # 3. Save embedding for future use.
    if CACHE_AVAILABLE:
        cache.setex(
            key,
            EMBED_TTL,
            json.dumps(embedding)
        )

    return embedding


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Create embeddings for many texts efficiently.

    It:
    1. Reads cached vectors from Redis.
    2. Sends only uncached text to BGE.
    3. Processes text in batches.
    4. Returns results in the original order.
    """
    if not texts:
        return []

    results = [None] * len(texts)

    uncached_texts = []
    uncached_indexes = []

    # Check Redis one text at a time.
    for index, text in enumerate(texts):
        if not text or not text.strip():
            results[index] = []
            continue

        key = _cache_key(text)

        if CACHE_AVAILABLE:
            cached = cache.get(key)

            if cached:
                results[index] = json.loads(cached)
                continue

        uncached_texts.append(text)
        uncached_indexes.append(index)

    cache_hits = len(texts) - len(uncached_texts)

    print(
        f"  Cache hits: {cache_hits}, "
        f"To embed: {len(uncached_texts)}"
    )

    # Create only missing embeddings.
    if uncached_texts:
        model = get_model()

        for start in range(
            0,
            len(uncached_texts),
            BATCH_SIZE
        ):
            end = start + BATCH_SIZE

            batch_texts = uncached_texts[start:end]
            batch_indexes = uncached_indexes[start:end]

            print(
                f"  Embedding batch "
                f"{start // BATCH_SIZE + 1}/"
                f"{(len(uncached_texts) - 1) // BATCH_SIZE + 1}"
            )

            batch_embeddings = model.encode(
                batch_texts,
                batch_size=BATCH_SIZE,
                show_progress_bar=False,
                normalize_embeddings=True
            ).tolist()

            # Put each embedding back into its original position.
            for original_index, embedding, text in zip(
                batch_indexes,
                batch_embeddings,
                batch_texts
            ):
                results[original_index] = embedding

                if CACHE_AVAILABLE:
                    cache.setex(
                        _cache_key(text),
                        EMBED_TTL,
                        json.dumps(embedding)
                    )

    return results