import chromadb
from sentence_transformers import SentenceTransformer

# ── Connect to ChromaDB ──────────────────────────────────────
# Same path where ingestion stored the data
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("policy_documents")

# ── Load BGE model ───────────────────────────────────────────
# Same model used during ingestion
model = SentenceTransformer("BAAI/bge-small-en-v1.5")


def retrieve(question, top_k=5):
    """
    Takes a question and returns top_k most relevant chunks
    from ChromaDB
    """

    # Step 1: Convert question to numbers (embedding)
    print(f"  Embedding question...")
    question_embedding = model.encode(question).tolist()

    # Step 2: Search ChromaDB for similar chunks
    print(f"  Searching ChromaDB...")
    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=top_k
    )

    # Step 3: Format results
    chunks = []
    for i, doc in enumerate(results["documents"][0]):
        chunks.append({
            "text": doc,
            "source": results["metadatas"][0][i]["source"],
            "distance": results["distances"][0][i]  # similarity score
        })

    return chunks