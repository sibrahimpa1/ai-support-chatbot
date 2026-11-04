"""Synthetic history so the support dashboard has two weeks of realistic data on first run.

Seeded rows are written straight to the store with past timestamps; live chats
from the widget go through the real pipeline and show up next to them.
"""

from __future__ import annotations

import random
from datetime import timedelta

from app.store import Store, iso, utcnow

NAMES = [
    "Alex Kim", "Sam Rivera", "Jordan Lee", "Riley Chen", "Casey Novak", "Taylor Brooks",
    "Morgan Diaz", "Jamie Park", "Avery Shah", "Quinn Murphy", "Drew Patel", "Rowan Silva",
    "Emerson Gray", "Harper Ito", "Skyler Moss", "Dakota Reyes", "Reese Okafor", "Parker Lund",
]

# (intent, customer message, bot reply, escalation reason or None, priority)
SCENARIOS = [
    ("order_status", "Where is my order FW-10234?",
     "Order FW-10234 (Ridgeline 2P Tent, Trail Mug) is currently **Shipped**, estimated delivery: Thursday.", None, None),
    ("shipping", "How long does express shipping take?",
     "Express shipping takes 1-2 business days and costs $19.95 on any order.", None, None),
    ("shipping", "Do you ship to Canada?",
     "Yes, we ship to Canada, the UK, the EU and Australia. International delivery takes 7-14 business days; duties are paid by the customer.", None, None),
    ("returns_refunds", "How do I return a jacket that doesn't fit?",
     "Go to Account > Orders, choose the order and click \"Start a return\". Exchanges for a different size are free.", None, None),
    ("returns_refunds", "When will I get my refund?",
     "Refunds are issued within 3 business days after the warehouse receives your return; your bank may take 5-10 more days.", None, None),
    ("billing", "Can I use two promo codes on one order?",
     "Only one promo code can be used per order, and codes can't be applied to orders that were already placed.", None, None),
    ("account", "I forgot my password",
     "Click \"Sign in\" and then \"Forgot password\". The reset link is valid for 30 minutes.", None, None),
    ("product_info", "Do your hiking boots run small?",
     "Our hiking boots run half a size small, so we recommend ordering half a size up.", None, None),
    ("product_info", "Is the tent covered by warranty?",
     "All Fernway-brand gear has a lifetime warranty against defects in materials and workmanship.", None, None),
    ("store_info", "What are your store hours in Denver?",
     "Our flagship store at 1450 Larimer Street is open daily from 10 AM to 7 PM.", None, None),
    ("order_change", "Can I cancel my order? I placed it 20 minutes ago",
     "Orders can be cancelled within 1 hour of being placed. Open the order under Account > Orders and click \"Cancel order\".", None, None),
    ("billing", "I was charged twice for the same order and it's still there after a week",
     "I've passed this to a billing specialist who will investigate the duplicate charge.", "Billing error needs manual review", "high"),
    ("human_handoff", "Can I talk to a real person please?",
     "Of course. I've connected you with our support team.", "Customer requested a human agent", "normal"),
    ("complaint", "This is the second time my package arrived damaged. Unacceptable!",
     "I'm really sorry about this experience. I've flagged your conversation as a priority.", "Frustrated customer / complaint", "high"),
    ("product_info", "My tent pole snapped on the first trip, can I get it fixed under warranty?",
     "Warranty claims are reviewed by our team. I've passed your photos request to a specialist.", "Warranty claim needs manual action", "normal"),
    ("other", "Do you sell fishing licenses?",
     "I don't want to give you a wrong answer, so I've passed your question to our support team.", "Low confidence (0.22)", "low"),
]
# Relative frequency of each scenario (automated ones dominate, like a real queue).
WEIGHTS = [10, 7, 4, 9, 6, 4, 5, 4, 3, 3, 3, 2, 3, 2, 2, 2]
AGENTS = ["Maya (Tier 1)", "Luis (Billing)", "Priya (Tier 2)"]


def seed_demo_data(store: Store, conversations: int = 420, days: int = 30, seed: int = 7) -> int:
    if store.count_conversations() > 0:
        return 0
    with store.batch():
        return _seed(store, conversations, days, seed)


def _seed(store: Store, conversations: int, days: int, seed: int) -> int:
    rng = random.Random(seed)
    now = utcnow()
    created = 0
    for _ in range(conversations):
        # Volume grows toward today (the bot was rolled out recently), with quieter weekends.
        day_offset = min(int(rng.triangular(0, days, 0)), days - 1)
        if (now - timedelta(days=day_offset)).weekday() >= 5 and rng.random() < 0.4:
            day_offset = min(day_offset + 2, days - 1)
        start = now - timedelta(days=day_offset, hours=rng.randint(0, 10), minutes=rng.randint(0, 59))
        if start > now - timedelta(minutes=5):
            start = now - timedelta(minutes=rng.randint(5, 120))
        intent, question, reply, reason, priority = rng.choices(SCENARIOS, weights=WEIGHTS)[0]
        name = rng.choice(NAMES)
        email = name.split()[0].lower() + "@example.com"

        conv = store.create_conversation(name, email, at=start)
        store.add_message(conv["id"], "user", question, at=start)
        response_ms = int(rng.gauss(1400, 350))
        bot_at = start + timedelta(milliseconds=response_ms)
        confidence = round(rng.uniform(0.72, 0.97), 2) if reason is None else round(rng.uniform(0.15, 0.6), 2)
        store.add_message(conv["id"], "assistant", reply, intent=intent, confidence=confidence,
                          response_ms=max(response_ms, 350), at=bot_at)

        if reason is None:
            resolved = rng.random() < 0.85
            csat = (5 if rng.random() < 0.9 else 1) if rng.random() < 0.6 else None
            store.update_conversation(conv["id"], at=bot_at, intent=intent, csat=csat,
                                      status="resolved" if resolved else "bot_active")
        else:
            ticket = store.create_ticket(conv["id"], reason=reason, priority=priority or "normal",
                                         category=intent, summary=f'First message: "{question}"',
                                         at=bot_at)
            age_hours = (now - bot_at).total_seconds() / 3600
            fields: dict = {}
            if age_hours > 6 or rng.random() < 0.4:
                first_reply = bot_at + timedelta(minutes=rng.uniform(2, 35))
                agent = rng.choice(AGENTS)
                store.add_message(conv["id"], "agent",
                                  f"Hi {name.split()[0]}, this is {agent.split()[0]} from Fernway support. I'm looking into this for you now.",
                                  at=first_reply)
                fields |= {"first_agent_reply_at": iso(first_reply), "assignee": agent, "status": "in_progress"}
                if age_hours > 6:
                    resolved_at = first_reply + timedelta(minutes=rng.uniform(10, 180))
                    fields |= {"status": "resolved", "resolved_at": iso(resolved_at)}
            if fields:
                store.update_ticket(ticket["id"], **fields)
            closed = fields.get("status") == "resolved"
            store.update_conversation(conv["id"], at=bot_at, intent=intent,
                                      status="closed" if closed else "escalated",
                                      csat=(5 if rng.random() < 0.75 else 1) if closed and rng.random() < 0.5 else None)
        created += 1
    return created
