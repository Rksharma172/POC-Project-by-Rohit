from __future__ import annotations

import httpx

from app.core.exceptions import LLMProviderError
from app.core.logging import get_logger
from app.utils.retry import with_retry

from .base import BaseLLMProvider, LLMResponse

logger = get_logger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider (e.g. Qwen2.5, Llama3)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def provider_name(self) -> str:
        return "ollama"

    def model_name(self) -> str:
        return self._model

    @with_retry(max_attempts=3)
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": temperature if temperature is not None else self._temperature,
                "num_predict": max_tokens if max_tokens is not None else self._max_tokens,
            },
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self._base_url}/api/chat", json=payload
                )
                resp.raise_for_status()
                data = resp.json()
            content = data.get("message", {}).get("content", "")
            return LLMResponse(
                content=content,
                model=self._model,
                usage={},
                finish_reason=data.get("done_reason", "stop"),
            )
        except Exception as exc:
            logger.error("ollama_completion_failed", error=str(exc))
            raise LLMProviderError(f"Ollama completion failed: {exc}") from exc
