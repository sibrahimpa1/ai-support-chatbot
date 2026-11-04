import pytest

from app.intents import analyze, extract_order_ids


@pytest.mark.parametrize(
    "text, intent",
    [
        ("Where is my order?", "order_status"),
        ("How do I return my jacket for a refund?", "returns_refunds"),
        ("Do you ship to Canada? How much is international shipping?", "shipping"),
        ("I was charged twice on my card", "billing"),
        ("I forgot my password", "account"),
        ("Can I speak to a real person?", "human_handoff"),
        ("Hi! Can I cancel my order?", "order_change"),
        ("thanks, bye", "thanks"),
    ],
)
def test_intent_classification(text, intent):
    assert analyze(text).intent == intent


def test_unknown_topic_has_low_confidence():
    result = analyze("What's the capital of Peru?")
    assert result.intent == "other"
    assert result.confidence < 0.3


def test_negative_sentiment_is_detected():
    assert analyze("This is ridiculous, I'm so frustrated!!").sentiment <= -0.6
    assert analyze("Where is my order?").sentiment == 0


def test_order_id_extraction():
    assert extract_order_ids("my order is fw-10234 and FW 10235") == ["FW-10234", "FW-10235"]


def test_return_request_beats_product_words():
    assert analyze("Can I return it if the tent doesn't fit in my car?").intent == "returns_refunds"
