from src.workers.celery_app import celery_app
from src.ingestion.parsers.parser_router import load_documents
from src.ingestion.chunker import chunk_documents
from src.vectordb.chroma_manager import (
    store_chunks, clear_db
)
from src.cache.redis_cache import clear_cache


@celery_app.task(bind=True)
def process_document(self, folder="documents"):
    """
    Background task for document ingestion
    Runs asynchronously so API stays responsive
    """
    try:
        # Update task status
        self.update_state(
            state="PROGRESS",
            meta={"step": "Parsing documents..."}
        )
        docs = load_documents(folder)

        self.update_state(
            state="PROGRESS",
            meta={"step": f"Chunking {len(docs)} documents..."}
        )
        chunks = chunk_documents(docs)

        self.update_state(
            state="PROGRESS",
            meta={"step": f"Embedding {len(chunks)} chunks..."}
        )
        store_chunks(chunks)

        # Clear answer cache
        clear_cache()

        return {
            "status"  : "complete",
            "docs"    : len(docs),
            "chunks"  : len(chunks)
        }

    except Exception as e:
        return {
            "status": "failed",
            "error" : str(e)
        }