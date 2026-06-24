import hashlib

import chromadb

from src.config_loader import load_config


config = load_config()

COLLECTION_METADATA = {
    "hnsw:space": "cosine"
}

client = chromadb.PersistentClient(
    path=config["vectordb"]["persist_directory"]
)

collection = client.get_or_create_collection(
    name=config["vectordb"]["collection_name"],
    metadata=COLLECTION_METADATA
)


def get_collection():
    """
    Return the persistent ChromaDB collection.

    Cosine distance is used because BGE embeddings are normalized.
    """
    global collection

    collection = client.get_or_create_collection(
        name=config["vectordb"]["collection_name"],
        metadata=COLLECTION_METADATA
    )

    return collection


def remove_duplicates(
    chunks: list[dict],
    col=None
) -> list[dict]:
    """
    Remove duplicate chunks already present in ChromaDB
    and duplicate chunks inside the new incoming list.
    """
    seen_hashes = set()
    unique_chunks = []

    if col is None:
        col = get_collection()

    try:
        existing = col.get()

        for document in existing.get("documents", []):
            if document:
                document_hash = hashlib.md5(
                    document.encode("utf-8")
                ).hexdigest()

                seen_hashes.add(document_hash)

    except Exception as error:
        print(f"  Could not check existing chunks: {error}")

    for chunk in chunks:
        chunk_hash = hashlib.md5(
            chunk["text"].encode("utf-8")
        ).hexdigest()

        if chunk_hash not in seen_hashes:
            seen_hashes.add(chunk_hash)
            unique_chunks.append(chunk)

    removed = len(chunks) - len(unique_chunks)

    if removed > 0:
        print(f"  Removed {removed} duplicate chunks")

    return unique_chunks


def store_chunks(chunks: list[dict]):
    """
    Create BGE embeddings and store chunks in ChromaDB.
    """
    from src.ingestion.embedder import get_embeddings_batch

    print(f"\n  Storing {len(chunks)} chunks...")

    col = get_collection()

    chunks = remove_duplicates(chunks, col)

    print(f"  After dedup: {len(chunks)} chunks")

    if not chunks:
        print("  No new chunks to store")
        return

    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    sources = [
        chunk["source"]
        for chunk in chunks
    ]

    print(f"  Batch embedding {len(texts)} texts...")

    embeddings = get_embeddings_batch(texts)

    print("  Batch embedding complete")

    existing_count = col.count()

    ids = [
        f"chunk_{existing_count + index}"
        for index in range(len(chunks))
    ]

    metadatas = [
        {"source": source}
        for source in sources
    ]

    batch_size = 100

    for start in range(0, len(chunks), batch_size):
        end = start + batch_size

        col.add(
            ids=ids[start:end],
            documents=texts[start:end],
            metadatas=metadatas[start:end],
            embeddings=embeddings[start:end]
        )

        print(
            f"  Stored "
            f"{min(end, len(chunks))}/{len(chunks)}"
        )

    print(
        f"\n  Stored {len(chunks)} chunks "
        f"in ChromaDB"
    )


def verify_db():
    """
    Print a small ChromaDB summary.
    """
    col = get_collection()

    count = col.count()

    print(f"\n  ChromaDB: {count} chunks stored")

    if count > 0:
        sample = col.peek(limit=3)

        sources = list(set(
            metadata["source"]
            for metadata in sample["metadatas"]
            if metadata and "source" in metadata
        ))

        print(f"  Sources: {sources}")


def clear_db():
    """
    Delete the old collection and create a fresh cosine-distance collection.

    Run this before re-ingesting after changing embedding configuration.
    """
    global collection

    try:
        client.delete_collection(
            config["vectordb"]["collection_name"]
        )

        print("  Old collection deleted")

    except Exception as error:
        print(f"  Delete collection: {error}")

    collection = client.get_or_create_collection(
        name=config["vectordb"]["collection_name"],
        metadata=COLLECTION_METADATA
    )

    print("  Fresh cosine collection created")
    print(
        f"  Collection count: "
        f"{collection.count()}"
    )