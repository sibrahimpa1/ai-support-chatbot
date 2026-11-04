"""The provider interface every LLM backend implements."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.intents import NLUResult
from app.knowledge_base import SearchResult


@dataclass
class GenerationRequest:
    company: str
    message: str
    history: list[dict[str, str]]  # [{"role": "user"|"assistant", "content": str}]
    context: list[SearchResult]
    nlu: NLUResult
    orders: dict[str, dict] = field(default_factory=dict)  # order lookups for this turn


@dataclass
class GenerationResult:
    answer: str
    intent: str
    confidence: float
    needs_human: bool = False
    escalation_reason: str | None = None
    sources: list[str] = field(default_factory=list)  # chunk ids the answer relies on


class LLMProvider(Protocol):
    name: str

    def generate(self, request: GenerationRequest) -> GenerationResult: ...
