import requests
import os

OLLAMA_HOST = os.getenv(
    "OLLAMA_URL",
    "http://host.docker.internal:11434"
)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_URL = f"{OLLAMA_HOST}/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"


def generate_answer(question, chunks):
    context_parts = []
    for i, chunk in enumerate(chunks):
        context_parts.append(
            f"\n--- Source {i+1}: {chunk.get('source', 'unknown')} ---\n"
            f"{chunk.get('text', '')}"
        )
    context = "\n".join(context_parts)

    prompt = f"""You are a helpful HR assistant.

You MUST follow these rules:
- Use ONLY the given context
- If answer is missing say: "I don't know based on provided documents"
- Be concise and clear
- Always mention source name

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
"""

    try:
        print(f"  Sending to Ollama: {OLLAMA_URL}")
        response = requests.post(
            OLLAMA_URL,
            json={
                "model" : OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "top_p"      : 0.9
                }
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json().get("response", "No response")

    except requests.exceptions.ConnectionError:
        return "Error: Cannot connect to Ollama. Make sure ollama is running."
    except requests.exceptions.Timeout:
        return "Error: Request timed out."
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            try:
                err = e.response.json().get("error", "")
                if "not found" in err.lower():
                    return (
                        f"Error: Ollama model '{OLLAMA_MODEL}' is not installed. "
                        f"Run: ollama pull {OLLAMA_MODEL}"
                    )
            except ValueError:
                pass
        return f"Unexpected error: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"