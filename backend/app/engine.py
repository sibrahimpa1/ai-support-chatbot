"""The support pipeline: NLU -> order lookup -> retrieval -> LLM -> escalation policy."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.intents import INTENTS, NLUResult, analyze
from app.knowledge_base import Retriever, load_chunks, tokenize
from app.providers import GenerationRequest, GenerationResult, LLMProvider
from app.providers.anthropic_provider import ProviderError
from app.providers.mock import MockProvider
from app.store import Store

log = logging.getLogger(__name__)

SMALL_TALK = {"greeting", "thanks"}
# Intents where a wrong automated answer costs money or trust: route to people faster.
SENSITIVE = {"billing", "complaint"}
# Which knowledge base files (by stem) each intent is expected to be answered from.
INTENT_SOURCES: dict[str, tuple[str, ...]] = {
    "order_status": ("orders", "shipping"),
    "order_change": ("orders",),
    "shipping": ("shipping",),
    "returns_refunds": ("returns",),
    "billing": ("billing",),
    "account": ("account",),
    "product_info": ("products",),
    "store_info": ("company",),
}


@dataclass
class EscalationDecision:
    escalate: bool
    reason: str | None = None
    priority: str = "normal"


def decide_escalation(
    nlu: NLUResult, result: GenerationResult, threshold: float, previous_low: bool
) -> EscalationDecision:
    """Escalation policy. Order matters: the first matching rule names the reason."""
    if nlu.wants_human or result.intent == "human_handoff":
        return EscalationDecision(True, "Customer requested a human agent", "normal")
    if nlu.sentiment <= -0.6 or nlu.intent == "complaint" or result.intent == "complaint":
        return EscalationDecision(True, "Frustrated customer / complaint", "high")
    if result.needs_human:
        return EscalationDecision(True, result.escalation_reason or "Model requested handoff", "normal")
    if nlu.needs_action:
        return EscalationDecision(True, "Needs manual action (damage, billing error or claim)", "normal")
    if result.intent in SMALL_TALK:
        return EscalationDecision(False)
    if result.confidence < threshold:
        return EscalationDecision(True, f"Low confidence ({result.confidence:.2f})", "normal")
    if previous_low and result.confidence < threshold + 0.15:
        return EscalationDecision(True, "Repeated uncertain answers", "normal")
    return EscalationDecision(False)


class SupportEngine:
    def __init__(self, settings: Settings, store: Store, provider: LLMProvider):
        self.settings = settings
        self.store = store
        self.provider = provider
        self.fallback = MockProvider()
        self.retriever = Retriever(load_chunks(settings.knowledge_base_dir))
        self.orders: dict[str, dict[str, Any]] = (
            json.loads(settings.orders_file.read_text()) if settings.orders_file.exists() else {}
        )

    # Public API -------------------------------------------------------------

    def handle_message(
        self,
        text: str,
        conversation_id: str | None = None,
        customer_name: str = "Guest",
        customer_email: str | None = None,
    ) -> dict[str, Any]:
        conv = self.store.get_conversation(conversation_id) if conversation_id else None
        if conv is None:
            conv = self.store.create_conversation(customer_name, customer_email)
        conv_id = conv["id"]

        history = self.store.get_messages(conv_id)
        user_msg = self.store.add_message(conv_id, "user", text)

        # Once a human owns the conversation the bot stays quiet.
        if conv["status"] == "escalated":
            return self._response(conv_id, None, user_msg, escalated=True, provider="human")

        started = time.perf_counter()
        nlu = analyze(text)
        context = self._retrieve(text, history, INTENT_SOURCES.get(nlu.intent, ()))
        orders = {oid: self.orders[oid] for oid in nlu.order_ids if oid in self.orders}
        request = GenerationRequest(
            company=self.settings.company_name,
            message=text,
            history=[
                {"role": m["role"] if m["role"] == "user" else "assistant", "content": m["content"]}
                for m in history
                if m["role"] in ("user", "assistant", "agent")
            ],
            context=context,
            nlu=nlu,
            orders=orders,
        )
        result, provider_name = self._generate(request)
        if result.intent not in INTENTS:
            result.intent = nlu.intent

        last_bot = next((m for m in reversed(history) if m["role"] == "assistant"), None)
        previous_low = bool(
            last_bot
            and last_bot["confidence"] is not None
            and last_bot["confidence"] < self.settings.escalation_threshold + 0.15
            and last_bot["intent"] not in SMALL_TALK
        )
        decision = decide_escalation(nlu, result, self.settings.escalation_threshold, previous_low)

        ticket = None
        answer = result.answer
        if decision.escalate:
            if result.intent in SENSITIVE and decision.priority == "normal":
                decision.priority = "high"
            ticket = self._escalate(conv_id, history, text, result, decision)
            answer = self._handoff_message(answer, result, decision, ticket["id"], provider_name)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        bot_msg = self.store.add_message(
            conv_id,
            "assistant",
            answer,
            intent=result.intent,
            confidence=result.confidence,
            response_ms=elapsed_ms,
            sources=result.sources,
        )
        fields: dict[str, Any] = {"intent": conv["intent"] or result.intent}
        if conv["intent"] in (None, "greeting", "thanks", "other"):
            fields["intent"] = result.intent
        if decision.escalate:
            fields["status"] = "escalated"
        elif result.intent == "thanks" and len(history) > 1:
            fields["status"] = "resolved"
        self.store.update_conversation(conv_id, **fields)

        return self._response(
            conv_id,
            bot_msg,
            user_msg,
            escalated=decision.escalate,
            provider=provider_name,
            ticket=ticket,
            nlu=nlu,
            decision=decision,
            context=context,
        )

    def escalate_manually(self, conv_id: str, reason: str = "Customer requested a human agent"):
        conv = self.store.get_conversation(conv_id)
        if conv is None:
            return None
        existing = self.store.open_ticket_for(conv_id)
        if existing:
            return existing
        history = self.store.get_messages(conv_id)
        result = GenerationResult(answer="", intent=conv["intent"] or "human_handoff", confidence=1.0)
        ticket = self._escalate(conv_id, history, "", result, EscalationDecision(True, reason))
        self.store.add_message(
            conv_id,
            "system",
            f"Conversation handed over to the support team (ticket #{ticket['id']}).",
        )
        self.store.update_conversation(conv_id, status="escalated")
        return ticket

    # Internals --------------------------------------------------------------

    def _retrieve(self, text: str, history: list[dict[str, Any]], boost: tuple[str, ...]):
        query = text
        # Short follow-ups ("and for Canada?") inherit the previous question's topic.
        if len(tokenize(text)) < 3:
            prev = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
            query = f"{prev} {text}"
        results = self.retriever.search(query, self.settings.retrieval_top_k, boost)
        if not results:
            return []
        best = results[0].score
        return [r for r in results if r.score >= best * 0.35]

    def _generate(self, request: GenerationRequest) -> tuple[GenerationResult, str]:
        try:
            return self.provider.generate(request), self.provider.name
        except ProviderError as exc:
            log.warning("Provider %s failed, using offline fallback: %s", self.provider.name, exc)
            return self.fallback.generate(request), f"{self.fallback.name} (fallback)"

    def _escalate(self, conv_id, history, text, result, decision) -> dict[str, Any]:
        first_question = next((m["content"] for m in history if m["role"] == "user"), text)
        summary = (
            f"Topic: {INTENTS.get(result.intent, result.intent)}. "
            f"First message: \"{first_question[:160]}\""
        )
        if text and text != first_question:
            summary += f" Latest: \"{text[:160]}\""
        return self.store.create_ticket(
            conv_id,
            reason=decision.reason or "Escalated",
            summary=summary,
            priority=decision.priority,
            category=result.intent,
        )

    @staticmethod
    def _handoff_message(answer, result, decision, ticket_id, provider_name) -> str:
        ref = f"(ticket #{ticket_id})"
        hours = "Our team is online Mon-Fri 8 AM-6 PM and Sat 9 AM-1 PM MT."
        if decision.reason == "Customer requested a human agent":
            return f"Of course. I've connected you with our support team {ref}. A specialist will reply right here in this chat. {hours}"
        if decision.reason == "Frustrated customer / complaint":
            return f"I'm really sorry about this experience. I've flagged your conversation as a priority for our support team {ref}, and a specialist will take it from here. {hours}"
        if (decision.reason or "").startswith("Needs manual action") and answer:
            return f"{answer}\n\nI've also opened ticket #{ticket_id} so a specialist can sort this out for you personally. They'll reply right here."
        if provider_name == "anthropic" and result.needs_human and answer:
            return f"{answer} {ref}"
        if answer and result.confidence >= 0.2:
            return f"{answer}\n\nI'm not fully sure this answers your question, so I've also passed it to our support team {ref}. {hours}"
        return f"I don't want to give you a wrong answer, so I've passed your question to our support team {ref}. A specialist will reply here shortly. {hours}"

    def _response(self, conv_id, bot_msg, user_msg, *, escalated, provider, ticket=None,
                  nlu=None, decision=None, context=None) -> dict[str, Any]:
        return {
            "conversation_id": conv_id,
            "user_message": user_msg,
            "reply": bot_msg,
            "escalated": escalated,
            "ticket": ticket,
            "provider": provider,
            "debug": {
                "nlu_intent": nlu.intent,
                "nlu_confidence": nlu.confidence,
                "sentiment": nlu.sentiment,
                "escalation_reason": decision.reason if decision else None,
                "retrieved": [
                    {"id": r.chunk.id, "title": r.chunk.title, "score": round(r.score, 2)}
                    for r in context or []
                ],
            }
            if nlu
            else None,
        }
