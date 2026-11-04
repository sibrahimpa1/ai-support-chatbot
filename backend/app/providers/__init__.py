"""Provider registry. Add a new LLM backend by implementing `LLMProvider`."""

from __future__ import annotations

from app.config import Settings
from app.providers.base import GenerationRequest, GenerationResult, LLMProvider
from app.providers.mock import MockProvider

__all__ = ["GenerationRequest", "GenerationResult", "LLMProvider", "build_provider"]


def build_provider(settings: Settings) -> LLMProvider:
    choice = settings.llm_provider.lower()
    if choice == "auto":
        choice = "anthropic" if settings.anthropic_api_key else "mock"
    if choice == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY")
        from app.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            settings.anthropic_api_key, settings.anthropic_model, settings.anthropic_effort
        )
    if choice == "mock":
        return MockProvider(settings.confidence_intent_weight)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")
