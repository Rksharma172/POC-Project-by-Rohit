import chromadb
from src.config_loader import load_config

config = load_config()

# ── Global client and collection ─────────────────────────────
client = chromadb.PersistentClient(
    path=config["vectordb"]["persist_directory"]
)

collection = client.get_or_create_collection(
    name=config["vectordb"]["collection_name"]
)


def get_collection():
    """
    Always returns fresh collection reference
    Fixes stale collection bug after clear_db()
    """
    global collection
    collection = client.get_or_create_collection(
        name=config["vectordb"]["collection_name"]
    )
    return collection


def store_chunks(chunks):
    from src.ingestion.embedder import get_embeddings_batch

    print(f"\n  Storing {len(chunks)} chunks...")

    # Always get fresh collection
    col = get_collection()

    # Step 1: Remove duplicates
    chunks = remove_duplicates(chunks, col)
    print(f"  After dedup: {len(chunks)} chunks")

    if not chunks:
        print("  No new chunks to store")
        return

    # Step 2: Extract texts and sources
    texts   = [chunk["text"]   for chunk in chunks]
    sources = [chunk["source"] for chunk in chunks]

    # Step 3: Batch embed
    print(f"  Batch embedding {len(texts)} texts...")
    embeddings = get_embeddings_batch(texts)
    print(f" Batch embedding complete")

    # Step 4: Store in batches
    existing_count = col.count()
    ids       = [f"chunk_{existing_count + i}"
                 for i in range(len(chunks))]
    metadatas = [{"source": source} for source in sources]

    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        end = i + batch_size
        col.add(
            ids        = ids[i:end],
            documents  = texts[i:end],
            metadatas  = metadatas[i:end],
            embeddings = embeddings[i:end]
        )
        print(f"  Stored {min(end, len(chunks))}/{len(chunks)}")

    print(f"\n Stored {len(chunks)} chunks in ChromaDB")


def remove_duplicates(chunks, col=None):
    import hashlib
    seen_hashes = set()
    unique_chunks = []

    if col is None:
        col = get_collection()

    # Get existing hashes from ChromaDB
    try:
        existing = col.get()
        for doc in existing.get("documents", []):
            if doc:
                h = hashlib.md5(doc.encode()).hexdigest()
                seen_hashes.add(h)
    except Exception as e:
        print(f" Could not check existing: {e}")

    for chunk in chunks:
        h = hashlib.md5(chunk["text"].encode()).hexdigest()
        if h not in seen_hashes:
            seen_hashes.add(h)
            unique_chunks.append(chunk)

    removed = len(chunks) - len(unique_chunks)
    if removed > 0:
        print(f" Removed {removed} duplicate chunks")

    return unique_chunks


def verify_db():
    col   = get_collection()
    count = col.count()
    print(f"\n ChromaDB: {count} chunks stored")
    if count > 0:
        sample  = col.peek(limit=3)
        sources = list(set(
            m["source"] for m in sample["metadatas"]
        ))
        print(f"  Sources: {sources}")


def clear_db():
    """
    Properly clears and recreates collection
    """
    global collection
    try:
        client.delete_collection(
            config["vectordb"]["collection_name"]
        )
        print(" Old collection deleted")
    except Exception as e:
        print(f"  Delete collection: {e}")

    # Recreate fresh empty collection
    collection = client.get_or_create_collection(
        name=config["vectordb"]["collection_name"]
    )
    print(" Fresh collection created")
    print(f"  Collection count: {collection.count()}")