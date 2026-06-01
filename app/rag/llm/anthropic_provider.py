from __future__ import annotations

import anthropic

from app.core.exceptions import LLMProviderError
from app.core.logging import get_logger
from app.utils.retry import with_retry

from .base import BaseLLMProvider, LLMResponse

logger = get_logger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def provider_name(self) -> str:
        return "anthropic"

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
            response = await self._client.messages.create(
                model=self._model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=temperature if temperature is not None else self._temperature,
                max_tokens=max_tokens if max_tokens is not None else self._max_tokens,
            )
            content = response.content[0].text if response.content else ""
            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            }
            return LLMResponse(
                content=content,
                model=self._model,
                usage=usage,
                finish_reason=response.stop_reason or "stop",
            )
        except Exception as exc:
            logger.error("anthropic_completion_failed", error=str(exc))
            raise LLMProviderError(f"Anthropic completion failed: {exc}") from exc
