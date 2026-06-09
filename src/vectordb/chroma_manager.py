import chromadb
from ..ingestion.embedder import get_embedding
from ..config_loader import load_config

config = load_config()

client = chromadb.PersistentClient(
    path=config["vectordb"]["persist_directory"]
)

collection = client.get_or_create_collection(
    name=config["vectordb"]["collection_name"]
)


def store_chunks(chunks):
    print(f"  Storing {len(chunks)} chunks...")
    for i, chunk in enumerate(chunks):
        print(f"    Embedding chunk {i+1}/{len(chunks)}...", end="\r")
        embedding = get_embedding(chunk["text"])
        collection.add(
            ids=[f"chunk_{i}"],
            documents=[chunk["text"]],
            metadatas=[{"source": chunk["source"]}],
            embeddings=[embedding]
        )
    print(f"\n  Stored {len(chunks)} chunks in ChromaDB")


def verify_db():
    count = collection.count()
    print(f"ChromaDB contains {count} chunks")
    if count > 0:
        sample = collection.peek(limit=2)
        print(f"Sample sources: {[m['source'] for m in sample['metadatas']]}")


def clear_db():
    client.delete_collection(config["vectordb"]["collection_name"])
    print("ChromaDB cleared successfully")