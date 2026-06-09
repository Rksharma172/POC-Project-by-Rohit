from ..config_loader import load_config

config = load_config()
CHUNK_SIZE = config["chunking"]["chunk_size"]
OVERLAP = config["chunking"]["chunk_overlap"]


def chunk_documents(docs):
    all_chunks = []

    for doc in docs:
        text = doc["text"]
        source = doc["source"]
        chunks = []

        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "source": source
                })

            start += CHUNK_SIZE - OVERLAP  # slide forward with overlap

        print(f"  Chunked {source}: {len(chunks)} chunks")
        all_chunks.extend(chunks)

    print(f"  Total chunks created: {len(all_chunks)}")
    return all_chunks