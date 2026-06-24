from src.config_loader import load_config
from src.ingestion.embedder import get_embedding
from src.vectordb.chroma_manager import get_collection


config = load_config()

DEFAULT_TOP_K = config["retrieval"]["top_k"]


def retrieve(question: str, top_k: int = DEFAULT_TOP_K):
    """
    Retrieve document chunks closest to the user's question.

    Uses the exact same BGE embedding function as ingestion,
    semantic chunking, and document storage.
    """
    print("  Embedding question...")

    question_embedding = get_embedding(question)

    if not question_embedding:
        return []

    collection = get_collection()

    total = collection.count()

    print(f"  Searching ChromaDB ({total} chunks)...")

    if total == 0:
        print("  ChromaDB is empty!")
        return []

    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=min(top_k, total)
    )

    chunks = []

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for index, document in enumerate(documents):
        metadata = (
            metadatas[index]
            if index < len(metadatas)
            else {}
        )

        distance = (
            distances[index]
            if index < len(distances)
            else 999
        )

        chunks.append({
            "text": document,
            "source": metadata.get("source", "unknown"),
            "distance": float(distance)
        })

    print(f"  Found {len(chunks)} chunks")

    for chunk in chunks:
        print(
            f"     -> {chunk['source']} "
            f"(distance: {chunk['distance']:.4f})"
        )

    return chunks