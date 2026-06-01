from __future__ import annotations

SYSTEM_PROMPT = """\
You are an Internal Policy Assistant for the organization.

Your responsibilities:
- Answer employee questions using ONLY the policy documents provided in the context below.
- Never invent, assume, or extrapolate information beyond what is explicitly stated in the documents.
- If the requested information is not present in the provided context, respond exactly with:
  "Information not found in current policy documents."
- Always cite the specific document and section from which each piece of information was drawn.
- Be concise, professional, and factual.
- Do not provide personal opinions or legal advice.

Context Documents:
{context}
"""

USER_PROMPT_TEMPLATE = """\
Question: {question}

Instructions:
1. Answer based solely on the context documents provided above.
2. After your answer, list all citations in this exact format:
   SOURCE: [Document Name] | Section: [Section Name] | Relevance: [high/medium/low]
3. If you cannot answer from the context, say exactly: "Information not found in current policy documents."
"""

ANSWER_EXTRACTION_PROMPT = """\
Given the following answer and citations, extract them into structured JSON.

Answer text:
{answer_text}

Return a JSON object with:
- "answer": the main answer text (without citations)
- "citations": list of {{"document": "...", "section": "...", "relevance": "..."}}
- "confidence": float 0.0-1.0 based on how directly the context supported the answer
"""


def build_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into a context block for the system prompt."""
    parts: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        doc_name = chunk.get("document_name", "Unknown")
        section = chunk.get("section", "")
        text = chunk.get("text", "")
        header = f"[{i}] {doc_name}"
        if section:
            header += f" — {section}"
        parts.append(f"{header}\n{text}")
    return "\n\n---\n\n".join(parts)


def build_prompts(question: str, chunks: list[dict]) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) ready to send to any LLM provider."""
    context = build_context(chunks)
    system = SYSTEM_PROMPT.format(context=context)
    user = USER_PROMPT_TEMPLATE.format(question=question)
    return system, user
