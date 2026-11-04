"""Claude provider: grounded answers with structured intent + escalation output."""

from __future__ import annotations

import json
import logging

import anthropic

from app.intents import INTENTS
from app.providers.base import GenerationRequest, GenerationResult

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the customer support assistant for {company}, an online outdoor gear store.
You chat with customers in a small website widget, so keep answers short (1-4 sentences),
friendly and concrete. Use markdown only for **bold** and short lists.

Answer only from the <knowledge_base> articles and <order_lookup> data in the user's turn.
If they do not contain the answer, do not guess policies, prices or dates: say you are not
sure, set needs_human to true and explain why in escalation_reason.

Also set needs_human to true when the customer asks for a person, is clearly upset,
reports a problem that needs a manual action (refund exceptions, damaged items, billing
errors, warranty claims), or the same issue is still unresolved after your earlier answers.
When needs_human is true, still write a helpful answer that tells the customer a support
specialist will take over in this chat.

confidence is your probability (0 to 1) that the answer fully resolves the customer's request.
cited_sources lists the ids of the articles you used."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "intent": {"type": "string", "enum": list(INTENTS)},
        "confidence": {"type": "number"},
        "needs_human": {"type": "boolean"},
        "escalation_reason": {"type": "string"},
        "cited_sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "answer",
        "intent",
        "confidence",
        "needs_human",
        "escalation_reason",
        "cited_sources",
    ],
    "additionalProperties": False,
}


class ProviderError(RuntimeError):
    pass


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, effort: str = "low"):
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=2, timeout=60.0)
        self.model = model
        self.effort = effort

    def _user_turn(self, request: GenerationRequest) -> str:
        articles = "\n".join(
            f'<article id="{r.chunk.id}" title="{r.chunk.source}: {r.chunk.title}">\n'
            f"{r.chunk.text}\n</article>"
            for r in request.context
        )
        orders = json.dumps(request.orders, indent=2) if request.orders else "none"
        hints = (
            f"pre-classifier intent={request.nlu.intent} "
            f"(confidence {request.nlu.confidence:.2f}), sentiment={request.nlu.sentiment:.2f}"
        )
        return (
            f"<knowledge_base>\n{articles or 'no matching articles'}\n</knowledge_base>\n"
            f"<order_lookup>\n{orders}\n</order_lookup>\n"
            f"<nlu_hints>{hints}</nlu_hints>\n\n"
            f"Customer message:\n{request.message}"
        )

    def generate(self, request: GenerationRequest) -> GenerationResult:
        messages = [*request.history[-10:], {"role": "user", "content": self._user_turn(request)}]
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT.format(company=request.company),
                messages=messages,
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
                },
                # Server-side refusal fallback: if a safety classifier declines,
                # the API re-runs the request on Anthropic's recommended model.
                extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
                extra_body={"fallbacks": "default"},
            )
        except anthropic.APIConnectionError as exc:
            raise ProviderError(f"Could not reach the Claude API: {exc}") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError("Claude API rate limit reached") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"Claude API error {exc.status_code}: {exc.message}") from exc

        if response.stop_reason == "refusal":
            return GenerationResult(
                answer="I'm not able to help with that here, so I'm passing you to a specialist.",
                intent=request.nlu.intent,
                confidence=0.0,
                needs_human=True,
                escalation_reason="Model declined the request",
            )

        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            log.warning("Unparseable model output (stop_reason=%s)", response.stop_reason)
            raise ProviderError("Model returned invalid JSON") from exc

        return GenerationResult(
            answer=data["answer"].strip(),
            intent=data["intent"],
            confidence=max(0.0, min(1.0, float(data["confidence"]))),
            needs_human=bool(data["needs_human"]),
            escalation_reason=data["escalation_reason"] or None,
            sources=list(data["cited_sources"]),
        )
