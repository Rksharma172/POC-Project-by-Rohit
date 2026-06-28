from src.config_loader import load_config
from src.retrieval.evidence import tokenize


config = load_config()

DEFAULT_TOP_K = config["retrieval"]["top_k"]
CANDIDATE_K = config["retrieval"].get("candidate_k", DEFAULT_TOP_K * 4)
VECTOR_WEIGHT = config["retrieval"].get("vector_weight", 0.68)
LEXICAL_WEIGHT = config["retrieval"].get("lexical_weight", 0.32)


def lexical_score(question: str, document: str) -> float:
    query_terms = tokenize(question)

    if not query_terms:
        return 0.0

    document_terms = tokenize(document)

    if not document_terms:
        return 0.0

    overlap = query_terms & document_terms
    return len(overlap) / len(query_terms)


def metadata_to_chunk(document, metadata, distance=999):
    return {
        "text": document,
        "source": metadata.get("source", "unknown"),
        "owner": metadata.get("owner", "default"),
        "content_type": metadata.get("content_type", "text"),
        "distance": float(distance)
    }


def retrieve(
    question: str,
    top_k: int = DEFAULT_TOP_K,
    owner: str = "default"
):
    """
    Retrieve document chunks closest to the user's question.

    Uses the exact same BGE embedding function as ingestion,
    semantic chunking, and document storage.
    """
    from src.ingestion.embedder import get_embedding
    from src.vectordb.chroma_manager import get_collection

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

    candidate_k = min(max(top_k, CANDIDATE_K), total)

    owner_filter = {"owner": owner}

    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=candidate_k,
        where=owner_filter
    )

    by_key = {}

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

        chunk = metadata_to_chunk(document, metadata, distance)
        chunk["vector_score"] = max(0.0, 1.0 - float(distance))
        chunk["lexical_score"] = lexical_score(question, document)
        key = (chunk["source"], document)
        by_key[key] = chunk

    all_user_data = collection.get(where=owner_filter)

    for document, metadata in zip(
        all_user_data.get("documents", []),
        all_user_data.get("metadatas", [])
    ):
        score = lexical_score(question, document)

        if score <= 0:
            continue

        key = (metadata.get("source", "unknown"), document)
        chunk = by_key.get(
            key,
            metadata_to_chunk(document, metadata)
        )
        chunk["lexical_score"] = max(
            chunk.get("lexical_score", 0.0),
            score
        )
        chunk.setdefault("vector_score", 0.0)
        by_key[key] = chunk

    chunks = list(by_key.values())

    for chunk in chunks:
        if chunk.get("content_type") == "table":
            table_boost = 0.08
        else:
            table_boost = 0.0

        chunk["hybrid_score"] = (
            VECTOR_WEIGHT * chunk.get("vector_score", 0.0)
            + LEXICAL_WEIGHT * chunk.get("lexical_score", 0.0)
            + table_boost
        )

    chunks.sort(
        key=lambda chunk: (
            chunk.get("hybrid_score", 0.0),
            -chunk.get("distance", 999)
        ),
        reverse=True
    )

    chunks = chunks[:top_k]

    print(f"  Found {len(chunks)} chunks")

    for chunk in chunks:
        print(
            f"     -> {chunk['source']} "
            f"(distance: {chunk['distance']:.4f}, "
            f"hybrid: {chunk.get('hybrid_score', 0):.3f})"
        )

    return chunks
