"""Offline provider: extractive answers straight from the knowledge base.

It lets anyone run the full product (widget, escalation, dashboard) without an
API key. Answers are stitched from the most relevant sentences of the best
matching knowledge base section, so they stay grounded, just less fluent.
"""

from __future__ import annotations

import re

from app.knowledge_base import tokenize
from app.providers.base import GenerationRequest, GenerationResult

_SMALL_TALK = {
    "greeting": "Hi there! I'm the {company} virtual assistant. I can help with orders, "
    "shipping, returns, billing and product questions. What can I do for you?",
    "thanks": "You're welcome! Is there anything else I can help you with today?",
}


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def format_order(order_id: str, order: dict) -> str:
    items = ", ".join(order["items"])
    status = order["status"]
    if status == "Cancelled":
        return f"Order {order_id} ({items}) was cancelled, and no payment was taken."
    line = f"Order {order_id} ({items}) is currently **{status}**"
    if order.get("eta"):
        line += f", estimated delivery: {order['eta']}"
    line += "."
    if order.get("tracking"):
        line += f" {order['carrier']} tracking number: {order['tracking']}."
    return line


class MockProvider:
    name = "mock"

    def __init__(self, intent_weight: float = 0.5):
        # How much the intent probability (vs. retrieval relevance) drives confidence.
        self.intent_weight = intent_weight

    def generate(self, request: GenerationRequest) -> GenerationResult:
        nlu = request.nlu

        if nlu.intent in _SMALL_TALK:
            return GenerationResult(
                answer=_SMALL_TALK[nlu.intent].format(company=request.company),
                intent=nlu.intent,
                confidence=0.95,
            )

        if request.orders:
            lines = [format_order(oid, o) for oid, o in request.orders.items()]
            return GenerationResult(
                answer=" ".join(lines) + " Anything else I can help with?",
                intent="order_status",
                confidence=0.92,
                sources=["orders"],
            )
        if nlu.intent == "order_status" and nlu.order_ids:
            return GenerationResult(
                answer=f"I couldn't find an order with the number {nlu.order_ids[0]}. "
                "Could you double-check it? It's in your confirmation email and looks like FW-10234.",
                intent="order_status",
                confidence=0.7,
            )
        if nlu.intent == "order_status" and not nlu.needs_action:
            return GenerationResult(
                answer="I can check that for you. What's your order number? "
                "It's in your confirmation email and looks like FW-10234.",
                intent="order_status",
                confidence=0.8,
            )

        if not request.context or (nlu.intent == "other" and nlu.source == "ml"):
            return GenerationResult(
                answer="I'm not sure I have the right answer for that.",
                intent=nlu.intent,
                confidence=0.15,
                needs_human=True,
                escalation_reason="No matching knowledge base article",
            )

        best = request.context[0]
        query_terms = set(tokenize(request.message))
        ranked = sorted(
            enumerate(_sentences(best.chunk.text)),
            key=lambda pair: len(query_terms & set(tokenize(pair[1]))),
            reverse=True,
        )
        # Keep the 2 most relevant sentences, in their original reading order.
        picked = sorted(ranked[:2], key=lambda pair: pair[0])
        answer = " ".join(sentence for _, sentence in picked)

        coverage = len(query_terms & set(tokenize(best.chunk.title + " " + best.chunk.text)))
        coverage /= max(len(query_terms), 1)
        relevance = coverage
        if best.similarity is not None:
            # bge cosine: ~0.55 is unrelated, ~0.8 is a close paraphrase.
            relevance = max(coverage, min(1.0, max(0.0, (best.similarity - 0.55) / 0.25)))
        w = self.intent_weight
        confidence = round(w * nlu.confidence + (1 - w) * relevance, 3)
        return GenerationResult(
            answer=answer,
            intent=nlu.intent,
            confidence=confidence,
            sources=[best.chunk.id],
        )
