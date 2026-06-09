import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../..")
))

from src.retrieval.retriever import retrieve
from src.retrieval.generator import generate_answer


def ask(question):
    print(f"\n{'='*50}")
    print(f"Question: {question}")
    print(f"{'='*50}")

    # Step 1: Retrieve
    print("\nStep 1: Retrieving chunks...")
    chunks = retrieve(question, top_k=5)
    print(f"  Found {len(chunks)} chunks")

    for i, chunk in enumerate(chunks):
        print(f"  {i+1}. {chunk['source']} "
              f"(score: {chunk['distance']:.4f})")
        print(f"     {chunk['text'][:100]}...")

    # Step 2: Generate
    print("\nStep 2: Generating answer...")
    answer = generate_answer(question, chunks)

    # Step 3: Show result
    print(f"\n{'='*50}")
    print(f"Answer:\n{answer}")
    print(f"{'='*50}")

    sources = list(set(chunk["source"] for chunk in chunks))
    print(f"\nSources: {sources}")

    return answer


def chat():
    print(" AskPolicy RAG System")
    print("Type your question and press Enter")
    print("Type 'exit' to quit\n")

    while True:
        question = input("You: ").strip()
        if question.lower() == "exit":
            print("Goodbye!")
            break
        if not question:
            continue
        ask(question)


if __name__ == "__main__":
    chat()