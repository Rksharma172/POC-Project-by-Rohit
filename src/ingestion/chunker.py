import re
from src.config_loader import load_config

config = load_config()
CHUNK_SIZE = config["chunking"]["chunk_size"]
OVERLAP    = config["chunking"]["chunk_overlap"]
MIN_CHUNK  = config["chunking"]["min_chunk_size"]
STRATEGY   = config["chunking"]["strategy"]


def semantic_chunk(text, source):
    chunks = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    if len(paragraphs) <= 1:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    if len(paragraphs) <= 1:
        paragraphs = re.split(r'(?<=[.!?])\s+', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

    print(f"    Split into {len(paragraphs)} initial segments")

    current_chunk = ""

    for para in paragraphs:
        if len(para) > CHUNK_SIZE:
            if len(current_chunk) >= MIN_CHUNK:
                chunks.append({"text": current_chunk.strip(), "source": source})
                current_chunk = ""

            start = 0
            while start < len(para):
                end = start + CHUNK_SIZE
                piece = para[start:end].strip()
                if piece and len(piece) >= MIN_CHUNK:
                    chunks.append({"text": piece, "source": source})
                start += CHUNK_SIZE - OVERLAP
            continue

        if len(current_chunk) + len(para) > CHUNK_SIZE:
            if len(current_chunk) >= MIN_CHUNK:
                chunks.append({"text": current_chunk.strip(), "source": source})

            overlap_text  = current_chunk[-OVERLAP:] if current_chunk else ""
            current_chunk = overlap_text + para + "\n\n"
        else:
            current_chunk += para + "\n\n"

    if current_chunk.strip() and len(current_chunk) >= MIN_CHUNK:
        chunks.append({"text": current_chunk.strip(), "source": source})

    return chunks


def fixed_chunk(text, source):
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk_text = text[start:end].strip()
        if chunk_text and len(chunk_text) >= MIN_CHUNK:
            chunks.append({"text": chunk_text, "source": source})
        start += CHUNK_SIZE - OVERLAP
    return chunks


def chunk_documents(docs):
    all_chunks = []

    for doc in docs:
        text   = doc["text"]
        source = doc["source"]

        print(f"  Chunking {source} ({len(text)} chars) strategy={STRATEGY}...")

        if STRATEGY == "semantic":
            chunks = semantic_chunk(text, source)
        else:
            chunks = fixed_chunk(text, source)

        expected_min_chunks = max(1, len(text) // (CHUNK_SIZE * 2))
        if len(chunks) < expected_min_chunks:
            print(f"    Only {len(chunks)} chunks for {len(text)} chars — forcing fixed_chunk")
            chunks = fixed_chunk(text, source)

        if not chunks:
            chunks = fixed_chunk(text, source)

        print(f"  {source}: {len(chunks)} chunks")
        all_chunks.extend(chunks)

    print(f"\n  Total chunks: {len(all_chunks)}")
    return all_chunks