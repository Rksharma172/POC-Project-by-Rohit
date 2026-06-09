import requests


def generate_answer(question, chunks):
    # Build context from chunks
    context = ""
    for i, chunk in enumerate(chunks):
        context += f"\n--- Source {i+1}: {chunk['source']} ---\n"
        context += chunk["text"] + "\n"

    # Build prompt
    prompt = f"""You are a helpful HR assistant that answers questions 
based only on the company policy documents provided below.

Rules:
- Answer only from the context provided
- If answer is not in context say "I don't know based on provided documents"
- Keep answer clear and concise
- Always mention which document the answer comes from

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:"""

    print(f"  Sending to Qwen 2.5:7b...")
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen2.5:7b",
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        if response.status_code == 200:
            return response.json()["response"]
        else:
            return f"Error from Ollama: {response.status_code}"

    except requests.exceptions.ConnectionError:
        return "Error: Ollama is not running. Please run 'ollama serve' first."

    except Exception as e:
        return f"Error: {e}"