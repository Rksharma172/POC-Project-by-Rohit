from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    raw: Any = None

    @property
    def prompt_tokens(self) -> int:
        return self.usage.get("prompt_tokens", 0)

    @property
    def completion_tokens(self) -> int:
        return self.usage.get("completion_tokens", 0)

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


class BaseLLMProvider(ABC):
    """Abstract base for all LLM providers.

    Swap providers by implementing this interface — business logic is untouched.
    """

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate a completion given system + user prompts."""

    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier."""

    @abstractmethod
    def model_name(self) -> str:
        """Model identifier used for this instance."""

    async def health_check(self) -> bool:
        """Return True if the provider is reachable."""
        try:
            resp = await self.complete(
                system_prompt="You are a health-check assistant.",
                user_prompt="Reply with: OK",
                max_tokens=5,
            )
            return bool(resp.content)
        except Exception:
            return False
