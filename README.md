# AskPolicy — Internal Policy Q&A

> Enterprise RAG system for HR policies, SOPs, and compliance documents.  
> Employees upload documents. Employees ask questions. The system answers — grounded, cited, and never hallucinated.

---

## Quick Start

```bash
# 1. Clone and set up environment
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY at minimum

# 2. Install dependencies
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Run the API
uvicorn app.main:app --reload --port 8000

# 4. Run ingest_pipeline.py file for storing chunks into vector database.
.\venv\Scripts\python.exe src\ingest_pipeline.py

# 5. For Retrieval part, run my rag_pipeline.py file
.\venv\Scripts\python.exe src\retrieval\rag_pipeline.py

# 6. For Frontend, run this command
.\venv\Scripts\python.exe -m uvicorn src.api:app --reload --port 8000