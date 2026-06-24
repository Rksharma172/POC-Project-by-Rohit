import os
import sys

# Add project root folder to Python path
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            ".."
        )
    )
)

from src.ingestion.parsers.parser_router import load_documents
from src.ingestion.chunker import chunk_documents
from src.vectordb.chroma_manager import (
    clear_db,
    store_chunks,
    verify_db
)


def run_ingestion(fresh_start=True):
    """
    Complete ingestion pipeline.

    fresh_start=True means:
    - Delete old ChromaDB collection
    - Create a fresh collection
    - Rebuild all chunks and embeddings from documents folder
    """

    print("\n" + "=" * 60)
    print("Starting AskPolicy Ingestion Pipeline")
    print("=" * 60 + "\n")

    # Step 0: Clear old database before rebuilding
    if fresh_start:
        print("Step 0: Clearing old ChromaDB collection...")
        clear_db()
        print()

    # Step 1: Load all supported documents
    print("Step 1: Loading documents...")
    docs = load_documents("documents")

    if not docs:
        print("\nNo documents were loaded.")
        print("Check whether your files are inside the documents folder.")
        return

    print(f"\nLoaded {len(docs)} document(s)\n")

    # Step 2: Create semantic chunks
    print("Step 2: Chunking documents...")
    chunks = chunk_documents(docs)

    if not chunks:
        print("\nNo chunks were created.")
        return

    print(f"\nCreated {len(chunks)} chunk(s)\n")

    # Step 3: Create BGE embeddings and store in ChromaDB
    print("Step 3: Creating embeddings and storing in ChromaDB...")
    store_chunks(chunks)

    # Step 4: Verify final database
    print("\nStep 4: Verifying ChromaDB...")
    verify_db()

    print("\n" + "=" * 60)
    print("Ingestion complete successfully.")
    print("=" * 60)


if __name__ == "__main__":
    run_ingestion(fresh_start=True)