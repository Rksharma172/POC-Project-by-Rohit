import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from src.retrieval.retriever import retrieve
from src.retrieval.generator import generate_answer

app = FastAPI(title="AskPolicy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


class QuestionRequest(BaseModel):
    question: str


class AnswerResponse(BaseModel):
    answer: str
    sources: list


@app.get("/")
def home():
    return {"status": "AskPolicy API is running ✅"}


@app.get("/chat")
def chat_ui():
    return FileResponse("templates/index.html")


@app.post("/ask")
def ask_question(request: QuestionRequest):
    print(f"\nReceived question: {request.question}")

    chunks = retrieve(request.question, top_k=5)
    answer = generate_answer(request.question, chunks)
    sources = list(set(chunk["source"] for chunk in chunks))

    return AnswerResponse(
        answer=answer,
        sources=sources
    )