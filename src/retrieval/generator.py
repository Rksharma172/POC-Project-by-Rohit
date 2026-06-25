import requests
import os
import re

# OLLAMA_HOST  = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")  # for docker container
OLLAMA_HOST = os.getenv("OLLAMA_URL", "http://localhost:11434") # using localhost
#OLLAMA_MODEL = "qwen2.5:7b"  
OLLAMA_MODEL = "qwen2.5:3b" 
OLLAMA_URL   = f"{OLLAMA_HOST}/api/generate"


def clean_answer_text(answer: str, sources: list) -> str:
    """
    Removes inline source mentions that Qwen sometimes adds
    directly inside the answer text, since sources are already
    shown separately below the answer in the UI.

    Example input:
    "AI is the broad field... Source: AI_GenAI_RAG_AgenticAI.pdf"

    Example output:
    "AI is the broad field..."
    """
    cleaned = answer

    # Remove patterns like "Source: filename.pdf" or "(Source: filename.pdf)"
    cleaned = re.sub(
        r'\(?\s*[Ss]ource[s]?\s*:\s*.+?\.(pdf|docx|xlsx|csv|html|txt|md)\)?\.?',
        '',
        cleaned
    )

    # Remove patterns like "according to filename.pdf" or "from filename.pdf"
    for src in sources:
        # escape special regex chars in filename
        escaped_src = re.escape(src)
        cleaned = re.sub(
            rf'\s*\(?\s*(according to|from|as per|based on)?\s*{escaped_src}\s*\)?\.?',
            '',
            cleaned,
            flags=re.IGNORECASE
        )

    # Clean up leftover double spaces, trailing punctuation, extra periods
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    cleaned = re.sub(r'\.\s*\.', '.', cleaned)
    cleaned = cleaned.strip()

    return cleaned


def generate_answer(question, chunks):
    context_parts = []
    sources = []
    for i, chunk in enumerate(chunks):
        source = chunk.get('source', 'unknown')
        sources.append(source)
        context_parts.append(
            f"\n--- Source {i+1} ---\n"
            f"{chunk.get('text', '')}"
        )
    context = "\n".join(context_parts)

    prompt = f"""You are a helpful HR assistant.

You MUST follow these rules:
- Use ONLY the given context
- If answer is missing say: "I don't know based on provided documents"
- Be concise and clear
- Do NOT mention document names, filenames, or say "Source:" anywhere
  in your answer — just answer the question naturally in plain text

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
        raw_answer = response.json().get("response", "No response")

        # Safety net: even if Qwen still mentions the filename,
        # strip it out programmatically
        clean = clean_answer_text(raw_answer, list(set(sources)))
        return clean if clean else raw_answer

    except requests.exceptions.ConnectionError:
        return "Error: Cannot connect to Ollama. Make sure ollama is running."
    except requests.exceptions.Timeout:
        return "Error: Request timed out."
    except Exception as e:
        return f"Unexpected error: {str(e)}"