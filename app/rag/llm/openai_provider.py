from __future__ import annotations

from openai import AsyncOpenAI

from app.core.exceptions import LLMProviderError
from app.core.logging import get_logger
from app.utils.retry import with_retry

from .base import BaseLLMProvider, LLMResponse

logger = get_logger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI chat completion provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def provider_name(self) -> str:
        return "openai"

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
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature if temperature is not None else self._temperature,
                max_tokens=max_tokens if max_tokens is not None else self._max_tokens,
            )
            choice = response.choices[0]
            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            logger.debug(
                "llm_completion",
                model=self._model,
                total_tokens=usage.get("total_tokens", 0),
            )
            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                usage=usage,
                finish_reason=choice.finish_reason or "stop",
                raw=response,
            )
        except Exception as exc:
            logger.error("openai_completion_failed", error=str(exc))
            raise LLMProviderError(f"OpenAI completion failed: {exc}") from exc
