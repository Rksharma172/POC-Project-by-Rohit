import sys
import os

# Add root folder to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingestion.parsers.parser_router import load_documents
from src.ingestion.chunker import chunk_documents
from src.vectordb.chroma_manager import store_chunks, verify_db, clear_db


def run_ingestion(fresh_start = True):
    print("Starting ingestion pipeline...\n")

    print("Step 1: Loading documents...")
    docs = load_documents("documents")
    if not docs:
        print("No documents loaded.")
        return
    print(f"Loaded {len(docs)} documents\n")

    print("Step 2: Chunking...")
    chunks = chunk_documents(docs)
    print(f"Created {len(chunks)} chunks\n")

    print("Step 3: Embedding + Storing...")
    store_chunks(chunks)

    print("\nVerifying...")
    verify_db()

    print("\nIngestion complete!")


if __name__ == "__main__":
    run_ingestion()