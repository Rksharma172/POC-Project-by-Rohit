import re
from src.config_loader import load_config

config = load_config()
CHUNK_SIZE    = config["chunking"]["chunk_size"]
OVERLAP       = config["chunking"]["chunk_overlap"]
MIN_CHUNK     = config["chunking"]["min_chunk_size"]
STRATEGY      = config["chunking"]["strategy"]


# ── Strategy 1: Semantic / Structure-aware chunking ──────────
def semantic_chunk(text, source):
    """
    Split text at natural boundaries:
    paragraphs → sentences → words
    Much better than fixed 500 chars
    """
    chunks = []

    # Step 1: Split by double newline (paragraphs)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    current_chunk = ""

    for para in paragraphs:
        # If adding this paragraph exceeds chunk size
        if len(current_chunk) + len(para) > CHUNK_SIZE:

            # Save current chunk if big enough
            if len(current_chunk) >= MIN_CHUNK:
                chunks.append({
                    "text": current_chunk.strip(),
                    "source": source
                })

            # Start new chunk with overlap
            # Take last OVERLAP chars from current chunk
            overlap_text = current_chunk[-OVERLAP:] if current_chunk else ""
            current_chunk = overlap_text + para + "\n\n"

        else:
            current_chunk += para + "\n\n"

    # Don't forget last chunk
    if current_chunk.strip() and len(current_chunk) >= MIN_CHUNK:
        chunks.append({
            "text": current_chunk.strip(),
            "source": source
        })

    return chunks


# ── Strategy 2: Heading-based chunking ───────────────────────
def heading_chunk(text, source):
    """
    Split text at headings
    Keeps each section together
    """
    chunks = []

    # Detect headings (ALL CAPS lines or lines ending with :)
    heading_pattern = re.compile(
        r'^([A-Z][A-Z\s]{3,}|.+:)\s*$',
        re.MULTILINE
    )

    sections = heading_pattern.split(text)
    current = ""

    for section in sections:
        if len(current) + len(section) > CHUNK_SIZE:
            if len(current) >= MIN_CHUNK:
                chunks.append({
                    "text": current.strip(),
                    "source": source
                })
            current = section
        else:
            current += "\n" + section

    if current.strip() and len(current) >= MIN_CHUNK:
        chunks.append({
            "text": current.strip(),
            "source": source
        })

    return chunks if chunks else fixed_chunk(text, source)


# ── Strategy 3: Fixed size chunking (original) ───────────────
def fixed_chunk(text, source):
    """
    Original fixed 500 char chunking
    Used as fallback
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + CHUNK_SIZE
        chunk_text = text[start:end].strip()

        if chunk_text and len(chunk_text) >= MIN_CHUNK:
            chunks.append({
                "text": chunk_text,
                "source": source
            })

        start += CHUNK_SIZE - OVERLAP

    return chunks


# ── Main chunking function ────────────────────────────────────
def chunk_documents(docs):
    all_chunks = []

    for doc in docs:
        text   = doc["text"]
        source = doc["source"]

        print(f"  Chunking {source} "
              f"({len(text)} chars) "
              f"strategy={STRATEGY}...")

        if STRATEGY == "semantic":
            chunks = semantic_chunk(text, source)

        elif STRATEGY == "heading":
            chunks = heading_chunk(text, source)

        else:
            chunks = fixed_chunk(text, source)

        # Fallback if no chunks created
        if not chunks:
            chunks = fixed_chunk(text, source)

        print(f"  {source}: {len(chunks)} chunks")
        all_chunks.extend(chunks)

    print(f"\n  Total chunks: {len(all_chunks)}")
    return all_chunks