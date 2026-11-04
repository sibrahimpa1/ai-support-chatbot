"""Fast rule-based NLU: intent, sentiment and entity extraction.

This runs on every message before any LLM call. It is cheap and deterministic,
so it is used for routing decisions that must never be left to chance (an
explicit request for a human, an angry customer) and as the full classifier
in offline mock mode. When Claude is enabled, its own intent label wins for
everything else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

INTENTS: dict[str, str] = {
    "greeting": "Greeting or small talk",
    "order_status": "Where is my order / order tracking",
    "order_change": "Change or cancel an order, update shipping address",
    "shipping": "Shipping options, costs, international delivery",
    "returns_refunds": "Returns, exchanges and refunds",
    "billing": "Payments, charges, promo codes, gift cards",
    "account": "Login, password, account settings, rewards",
    "product_info": "Product details, sizing, warranty, repairs",
    "store_info": "Store location, opening hours, contact details",
    "human_handoff": "Customer explicitly asks for a human agent",
    "complaint": "Customer is unhappy and wants the issue escalated",
    "thanks": "Thanks or goodbye",
    "other": "Anything outside the support domain",
}

# (pattern, weight). Patterns are matched against the lower-cased message.
_RULES: dict[str, list[tuple[str, float]]] = {
    "greeting": [(r"^(hi|hello|hey|good (morning|afternoon|evening))\b", 2.0)],
    "order_status": [
        (r"\bwhere(?:'s| is) my (order|package|parcel)", 3.0),
        (r"\b(track|tracking)\b", 2.0),
        (r"\border status\b", 3.0),
        (r"\b(hasn'?t|not|never) (arrived|shipped|come)", 2.0),
        (r"\bfw-\d{5}\b", 2.0),
        (r"\b(late|delayed|eta)\b", 1.0),
        (r"\b(package|parcel|delivery) (arrived|is|was)\b", 1.5),
        (r"\b(damaged|lost|missing|stolen)\b", 1.5),
    ],
    "order_change": [
        (r"\bcancel\b", 2.5),
        (r"\b(change|update|edit) (my |the )?(order|address|shipping address)", 3.0),
        (r"\bwrong address\b", 2.5),
    ],
    "shipping": [
        (r"\bship(ping)?\b", 1.5),
        (r"\bdeliver(y)?\b", 1.0),
        (r"\b(express|international|customs|free shipping|freight)\b", 2.0),
        (r"\bhow long\b", 1.0),
    ],
    "returns_refunds": [
        (r"\breturn(s|ing)?\b", 2.5),
        (r"\brefund(s|ed)?\b", 2.5),
        (r"\bexchange\b", 2.0),
        (r"\bsend (it )?back\b", 2.0),
        (r"\b(can i|how (do|can) i|want to|like to) (return|exchange|get a refund)", 2.0),
    ],
    "billing": [
        (r"\b(charge[sd]?|charged twice|double charge|billing|invoice)\b", 2.5),
        (r"\b(payment|pay|klarna|paypal|card)\b", 1.5),
        (r"\b(promo|discount|coupon) ?(code)?\b", 2.5),
        (r"\bgift card\b", 2.5),
        (r"\bprice (match|adjustment|drop)\b", 2.5),
    ],
    "account": [
        (r"\b(password|log ?in|sign ?in|account)\b", 2.0),
        (r"\b(rewards?|points|newsletter|unsubscribe)\b", 2.0),
        (r"\bdelete my (data|account)\b", 3.0),
    ],
    "product_info": [
        (r"\b(warranty|repair|defect(ive)?|broken)\b", 2.5),
        (r"\b(size|sizing|fit|runs (small|large))\b", 2.0),
        (r"\b(tent|jacket|boots?|backpack|kayak)\b", 1.0),
        (r"\b(in stock|restock|out of stock)\b", 2.0),
    ],
    "store_info": [
        (r"\b(store|shop) (hours|location|address)\b", 3.0),
        (r"\b(opening hours|open|phone number|email address|contact)\b", 1.5),
        (r"\b(support hours|pick ?up)\b", 2.0),
    ],
    "human_handoff": [
        (r"\b(human|real person|live agent|agent|representative|someone real)\b", 3.0),
        (r"\b(talk|speak|chat) (to|with) (a |an |someone|somebody)", 2.5),
        (r"\bcall me\b", 2.0),
    ],
    "complaint": [
        (r"\b(complain|complaint|unacceptable|ridiculous|worst|terrible|awful)\b", 3.0),
        (r"\b(manager|supervisor|lawyer|chargeback)\b", 2.5),
    ],
    "thanks": [(r"\b(thanks|thank you|thx|cheers|bye|goodbye)\b", 2.0)],
}

_NEGATIVE = re.compile(
    r"\b(angry|furious|upset|frustrated|annoyed|disappointed|unacceptable|ridiculous|"
    r"terrible|awful|worst|useless|scam|never again|waste|still waiting|again\?)\b"
)
# Problems the bot can explain but a person has to fix (refund, replacement, investigation).
_NEEDS_ACTION = re.compile(
    r"\b(arrived (damaged|broken)|(was|is|came) damaged|damaged|charged twice|double charged|"
    r"double charge|missing (item|items|from my order)|never (arrived|received)|stolen|"
    r"warranty claim|snapped|ripped|fell apart)\b"
)
_ORDER_ID = re.compile(r"\bfw-?\s?(\d{5})\b", re.IGNORECASE)


@dataclass
class NLUResult:
    intent: str
    confidence: float
    sentiment: float  # -1 (very negative) .. 0 (neutral)
    order_ids: list[str] = field(default_factory=list)
    needs_action: bool = False
    scores: dict[str, float] = field(default_factory=dict)

    @property
    def wants_human(self) -> bool:
        return self.intent == "human_handoff" or self.scores.get("human_handoff", 0) >= 3


def extract_order_ids(text: str) -> list[str]:
    return [f"FW-{m}" for m in _ORDER_ID.findall(text)]


def analyze(text: str) -> NLUResult:
    lowered = text.lower().strip()
    scores: dict[str, float] = {}
    for intent, rules in _RULES.items():
        score = sum(w for pattern, w in rules if re.search(pattern, lowered))
        if score:
            scores[intent] = score

    negatives = len(_NEGATIVE.findall(lowered))
    exclamations = min(lowered.count("!"), 3)
    sentiment = -min(1.0, 0.35 * negatives + 0.1 * exclamations)

    needs_action = bool(_NEEDS_ACTION.search(lowered))
    order_ids = extract_order_ids(text)
    if not scores:
        return NLUResult("other", 0.2, sentiment, order_ids, needs_action, scores)

    # A greeting followed by a real question should route on the question.
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if ranked[0][0] in ("greeting", "thanks") and len(ranked) > 1:
        ranked = ranked[1:] + ranked[:1]
    intent, top = ranked[0]
    total = sum(scores.values())
    # Confidence blends absolute evidence (how strong the match is) with
    # relative evidence (how clearly it beats the runner-up intents).
    absolute = min(1.0, top / 4.0)
    relative = top / total
    confidence = round(0.55 * absolute + 0.45 * relative, 3)
    return NLUResult(intent, confidence, sentiment, order_ids, needs_action, scores)
