import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collections = client.list_collections()

print("Collections in ChromaDB:")
for col in collections:
    count = client.get_collection(col.name).count()
    print(f"  -> {col.name} ({count} chunks)")