import re

import numpy as np

from src.config_loader import load_config
from src.ingestion.embedder import get_embeddings_batch


config = load_config()

CHUNK_SIZE = config["chunking"]["chunk_size"]
OVERLAP = config["chunking"]["chunk_overlap"]
MIN_CHUNK = config["chunking"]["min_chunk_size"]
STRATEGY = config["chunking"]["strategy"]

BREAKPOINT_PERCENTILE = config["chunking"].get(
    "semantic_breakpoint_percentile",
    20
)

MIN_SIMILARITY = config["chunking"].get(
    "semantic_min_similarity",
    0.65
)


def split_into_sentences(text: str) -> list[str]:
    """
    Convert document text into sentence-like units.

    It removes repeated spaces/newlines and splits after:
    . ! ? : ;
    """
    text = re.sub(r"\s+", " ", text).strip()

    sentences = re.split(
        r"(?<=[.!?])\s+|(?<=:)\s+|(?<=;)\s+",
        text
    )

    return [
        sentence.strip()
        for sentence in sentences
        if len(sentence.strip()) > 15
    ]


def get_overlap_sentences(
    sentences: list[str],
    overlap_chars: int
) -> list[str]:
    """
    Keep complete ending sentences as overlap.

    This is better than taking the last 120 characters because
    it does not cut a word or sentence in the middle.
    """
    overlap = []
    total_chars = 0

    for sentence in reversed(sentences):
        overlap.insert(0, sentence)

        total_chars += len(sentence) + 1

        if total_chars >= overlap_chars:
            break

    return overlap


def create_chunk(
    sentences: list[str],
    source: str,
    content_type: str = "text"
) -> dict | None:
    """
    Convert a list of sentences into one ChromaDB-ready chunk.
    """
    text = " ".join(sentences).strip()

    if len(text) < MIN_CHUNK:
        return None

    return {
        "text": text,
        "source": source,
        "content_type": content_type
    }


def fixed_chunk(text: str, source: str) -> list[dict]:
    """
    Backup method.

    Used when a document does not have enough usable sentences
    for embedding-based semantic chunking.
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + CHUNK_SIZE

        chunk_text = text[start:end].strip()

        if chunk_text and len(chunk_text) >= MIN_CHUNK:
            chunks.append({
                "text": chunk_text,
                "source": source,
                "content_type": "text"
            })

        start += max(1, CHUNK_SIZE - OVERLAP)

    return chunks


def embedding_semantic_chunk(
    text: str,
    source: str
) -> list[dict]:
    """
    True embedding-based semantic chunking.

    Process:
    1. Split document into sentences.
    2. Convert each sentence into a BGE vector.
    3. Compare neighboring sentence vectors.
    4. Start a new chunk when topic similarity falls.
    5. Preserve overlap and maximum chunk size.
    """
    sentences = split_into_sentences(text)

    if len(sentences) <= 1:
        return fixed_chunk(text, source)

    print(f"    Split into {len(sentences)} sentences")

    # BGE converts each sentence into a normalized embedding.
    embeddings = get_embeddings_batch(sentences)

    similarities = []

    # Compare sentence 1 with 2, 2 with 3, etc.
    for index in range(len(embeddings) - 1):
        current_embedding = np.array(embeddings[index])
        next_embedding = np.array(embeddings[index + 1])

        # Vectors are normalized.
        # Therefore dot product behaves like cosine similarity.
        similarity = float(
            np.dot(current_embedding, next_embedding)
        )

        similarities.append(similarity)

    if not similarities:
        return fixed_chunk(text, source)

    # Use both document-specific and safe minimum threshold.
    adaptive_threshold = float(
        np.percentile(
            similarities,
            BREAKPOINT_PERCENTILE
        )
    )

    threshold = max(
        MIN_SIMILARITY,
        adaptive_threshold
    )

    print(
        f"    Semantic breakpoint threshold: "
        f"{threshold:.3f}"
    )

    chunks = []
    current_sentences = []

    for index, sentence in enumerate(sentences):
        proposed_text = " ".join(
            current_sentences + [sentence]
        )

        # Rule 1: Never allow a chunk to become too large.
        if current_sentences and len(proposed_text) > CHUNK_SIZE:
            chunk = create_chunk(
                current_sentences,
                source
            )

            if chunk:
                chunks.append(chunk)

            current_sentences = get_overlap_sentences(
                current_sentences,
                OVERLAP
            )

        current_sentences.append(sentence)

        is_last_sentence = (
            index == len(sentences) - 1
        )

        # Rule 2: Create a new chunk at a semantic topic boundary.
        if not is_last_sentence:
            similarity = similarities[index]

            current_text = " ".join(
                current_sentences
            )

            topic_changed = similarity < threshold
            large_enough = (
                len(current_text) >= MIN_CHUNK
            )

            if topic_changed and large_enough:
                chunk = create_chunk(
                    current_sentences,
                    source
                )

                if chunk:
                    chunks.append(chunk)

                current_sentences = get_overlap_sentences(
                    current_sentences,
                    OVERLAP
                )

    # Store final remaining content.
    final_chunk = create_chunk(
        current_sentences,
        source
    )

    if final_chunk:
        chunks.append(final_chunk)

    return chunks


def split_table_blocks(text: str) -> list[dict]:
    """
    Separate parser-provided [TABLE] blocks from surrounding prose.

    Table chunks stay whole so row/column relationships are preserved
    during retrieval and answer generation.
    """
    pattern = re.compile(
        r"\[TABLE[^\]]*\].*?\[/TABLE\]",
        flags=re.DOTALL | re.IGNORECASE
    )

    blocks = []
    cursor = 0

    for match in pattern.finditer(text):
        before = text[cursor:match.start()].strip()

        if before:
            blocks.append({
                "text": before,
                "content_type": "text"
            })

        blocks.append({
            "text": match.group(0).strip(),
            "content_type": "table"
        })

        cursor = match.end()

    after = text[cursor:].strip()

    if after:
        blocks.append({
            "text": after,
            "content_type": "text"
        })

    return blocks or [{
        "text": text,
        "content_type": "text"
    }]


def chunk_table_block(text: str, source: str) -> list[dict]:
    if len(text) <= CHUNK_SIZE * 2:
        return [{
            "text": text,
            "source": source,
            "content_type": "table"
        }]

    rows = [
        row
        for row in text.splitlines()
        if row.strip()
    ]

    chunks = []
    current_rows = []

    for row in rows:
        proposed = "\n".join(current_rows + [row])

        if current_rows and len(proposed) > CHUNK_SIZE:
            chunks.append({
                "text": "\n".join(current_rows),
                "source": source,
                "content_type": "table"
            })
            current_rows = current_rows[-1:]

        current_rows.append(row)

    if current_rows:
        chunks.append({
            "text": "\n".join(current_rows),
            "source": source,
            "content_type": "table"
        })

    return chunks


def chunk_documents(docs: list[dict]) -> list[dict]:
    """
    Chunk every parsed document.
    """
    all_chunks = []

    for doc in docs:
        text = doc["text"]
        source = doc["source"]
        owner = doc.get("owner", "default")

        print(
            f"  Chunking {source} "
            f"({len(text)} chars), "
            f"strategy={STRATEGY}"
        )

        chunks = []

        for block in split_table_blocks(text):
            block_type = block["content_type"]
            block_text = block["text"]

            if block_type == "table":
                chunks.extend(
                    chunk_table_block(block_text, source)
                )
            elif STRATEGY == "semantic":
                chunks.extend(
                    embedding_semantic_chunk(
                        block_text,
                        source
                    )
                )
            else:
                chunks.extend(fixed_chunk(block_text, source))

        # Final safety fallback.
        if not chunks:
            print(
                "    Semantic chunking failed; "
                "using fixed chunking"
            )

            chunks = fixed_chunk(text, source)

        for chunk in chunks:
            chunk["owner"] = owner

        print(f"  {source}: {len(chunks)} chunks")

        all_chunks.extend(chunks)

    print(f"\nTotal chunks created: {len(all_chunks)}")

    return all_chunks
