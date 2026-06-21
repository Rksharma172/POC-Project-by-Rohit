import chromadb
from sentence_transformers import SentenceTransformer
from src.config_loader import load_config

config = load_config()

client = chromadb.PersistentClient(path=config["vectordb"]["persist_directory"])
model  = SentenceTransformer(config["embeddings"]["model"])


def get_collection():
    return client.get_or_create_collection(name=config["vectordb"]["collection_name"])


def retrieve(question, top_k=5):
    print(f"  Embedding question...")
    question_embedding = model.encode(question).tolist()

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
    for i, doc in enumerate(results["documents"][0]):
        chunks.append({
            "text"    : doc,
            "source"  : results["metadatas"][0][i]["source"],
            "distance": results["distances"][0][i]
        })

    print(f"  Found {len(chunks)} chunks")
    for c in chunks:
        print(f"     -> {c['source']} (distance: {c['distance']:.4f})")

    return chunks