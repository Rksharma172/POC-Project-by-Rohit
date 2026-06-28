import re


STOP_WORDS = {
    "about", "after", "again", "also", "and", "are", "based", "been",
    "before", "being", "between", "can", "could", "does", "for", "from",
    "has", "have", "how", "into", "its", "may", "more", "must", "not",
    "only", "policy", "provided", "shall", "should", "that", "the",
    "their", "then", "there", "this", "to", "was", "what", "when",
    "where", "which", "who", "will", "with", "you", "your"
}


def tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]{3,}", text.lower())
        if token not in STOP_WORDS
    }


def evidence_score(answer: str, chunks: list[dict]) -> float:
    answer_terms = tokenize(answer)

    if not answer_terms:
        return 0.0

    context_terms = tokenize(
        " ".join(chunk.get("text", "") for chunk in chunks)
    )

    if not context_terms:
        return 0.0

    overlap = answer_terms & context_terms
    return len(overlap) / max(1, len(answer_terms))


def is_evidence_supported(
    answer: str,
    chunks: list[dict],
    min_score: float = 0.35
) -> bool:
    lowered = (answer or "").lower()

    if "i don't know based on provided documents" in lowered:
        return True

    return evidence_score(answer, chunks) >= min_score
