from __future__ import annotations

import hashlib
import re


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    """Normalize whitespace, tabs, and line breaks for content-hash comparison."""
    text = text.lower()
    text = re.sub(r"[ \t]+", " ", text)        # collapse spaces/tabs
    text = re.sub(r"\r\n|\r|\n", "\n", text)   # normalize line endings
    text = re.sub(r"\n{2,}", "\n", text)        # collapse multiple newlines
    return text.strip()


def corpus_fingerprint(document_hashes: list[str]) -> str:
    """Deterministic fingerprint of the entire document corpus."""
    combined = "|".join(sorted(document_hashes))
    return sha256_of_text(combined)[:16]
