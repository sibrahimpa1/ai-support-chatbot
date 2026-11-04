"""The Claude provider is tested against a fake client, so no API key or network is needed."""

import json
from types import SimpleNamespace

import pytest

from app.intents import analyze
from app.knowledge_base import Chunk, SearchResult
from app.providers import GenerationRequest
from app.providers.anthropic_provider import AnthropicProvider, ProviderError


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def provider_with(response):
    provider = AnthropicProvider(api_key="test-key", model="claude-opus-5-5")
    provider.client = SimpleNamespace(messages=FakeMessages(response))
    return provider


def request(message="How long do refunds take?"):
    chunk = Chunk("returns#2", "Returns", "Refund timing", "Refunds are issued within 3 business days.")
    return GenerationRequest(
        company="Fernway Outdoor",
        message=message,
        history=[],
        context=[SearchResult(chunk, 3.2)],
        nlu=analyze(message),
    )


def text_response(payload, stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=json.dumps(payload)),
        ],
    )


def test_parses_structured_answer_and_grounds_prompt():
    provider = provider_with(text_response({
        "answer": "Refunds arrive within 3 business days.",
        "intent": "returns_refunds",
        "confidence": 0.93,
        "needs_human": False,
        "escalation_reason": "",
        "cited_sources": ["returns#2"],
    }))
    result = provider.generate(request())

    assert result.intent == "returns_refunds"
    assert result.confidence == 0.93
    assert result.sources == ["returns#2"]
    assert result.escalation_reason is None

    call = provider.client.messages.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert "<article id=\"returns#2\"" in call["messages"][-1]["content"]
    assert call["extra_body"] == {"fallbacks": "default"}


def test_refusal_escalates_instead_of_answering():
    provider = provider_with(SimpleNamespace(stop_reason="refusal", content=[]))
    result = provider.generate(request())
    assert result.needs_human and result.confidence == 0.0


def test_invalid_json_raises_provider_error():
    bad = SimpleNamespace(stop_reason="max_tokens", content=[SimpleNamespace(type="text", text="{\"answ")])
    with pytest.raises(ProviderError):
        provider_with(bad).generate(request())


def test_engine_falls_back_to_mock_when_claude_fails(settings):
    from app.engine import SupportEngine
    from app.store import Store

    class Broken:
        name = "anthropic"

        def generate(self, req):
            raise ProviderError("boom")

    engine = SupportEngine(settings, Store(":memory:"), Broken())
    body = engine.handle_message("How long do refunds take?")
    assert body["provider"] == "mock (fallback)"
    assert "3 business days" in body["reply"]["content"]
