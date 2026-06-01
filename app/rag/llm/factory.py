from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import ProviderNotSupportedError
from app.core.logging import get_logger

from .base import BaseLLMProvider

logger = get_logger(__name__)


class LLMFactory:
    """Creates the configured LLM provider.

    Add a new provider: implement BaseLLMProvider, register it here.
    """

    @staticmethod
    def create(settings: Settings) -> BaseLLMProvider:
        provider = settings.llm_provider.lower()
        logger.info("creating_llm_provider", provider=provider, model=settings.llm_model)

        if provider == "openai":
            from .openai_provider import OpenAIProvider
            return OpenAIProvider(
                api_key=settings.openai_api_key,
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )

        if provider == "azure_openai":
            from .azure_openai_provider import AzureOpenAIProvider
            return AzureOpenAIProvider(
                api_key=settings.azure_openai_api_key,
                endpoint=settings.azure_openai_endpoint,
                deployment=settings.azure_openai_deployment or settings.llm_model,
                api_version=settings.azure_openai_api_version,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )

        if provider == "anthropic":
            from .anthropic_provider import AnthropicProvider
            return AnthropicProvider(
                api_key=settings.anthropic_api_key,
                model=settings.yaml("llm", "anthropic_model", default="claude-3-5-sonnet-20241022"),
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )

        if provider in ("ollama", "qwen"):
            from .ollama_provider import OllamaProvider
            return OllamaProvider(
                base_url=settings.ollama_base_url,
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )

        raise ProviderNotSupportedError(
            f"LLM provider '{provider}' is not supported. "
            f"Supported: openai, azure_openai, anthropic, ollama, qwen"
        )
