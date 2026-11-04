from app.engine import decide_escalation
from app.intents import analyze
from app.providers import GenerationResult


def chat(client, message, conversation_id=None):
    res = client.post("/api/chat", json={"message": message, "conversation_id": conversation_id})
    assert res.status_code == 200
    return res.json()


def test_health_reports_mock_provider(client):
    body = client.get("/api/health").json()
    assert body["provider"] == "mock"
    assert body["knowledge_base_chunks"] > 0


def test_faq_question_is_answered_from_knowledge_base(client):
    body = chat(client, "How long do I have to return an item?")
    assert not body["escalated"]
    assert "60 days" in body["reply"]["content"]
    assert body["reply"]["sources"]


def test_order_lookup(client):
    body = chat(client, "Where is my order FW-10234?")
    assert "Shipped" in body["reply"]["content"]
    assert not body["escalated"]


def test_request_for_human_creates_ticket(client):
    first = chat(client, "Hi")
    body = chat(client, "I want to talk to a real person", first["conversation_id"])
    assert body["escalated"]
    ticket = body["ticket"]
    assert ticket["reason"] == "Customer requested a human agent"
    assert client.get("/api/tickets").json()[0]["id"] == ticket["id"]

    # The bot stays silent while a human owns the conversation.
    follow_up = chat(client, "hello?", first["conversation_id"])
    assert follow_up["reply"] is None


def test_off_topic_question_escalates_on_low_confidence(client):
    body = chat(client, "Can you recommend a good dentist in Chicago?")
    assert body["escalated"]
    assert "Low confidence" in body["ticket"]["reason"] or "No matching" in body["ticket"]["reason"]


def test_agent_reply_and_resolution_flow(client):
    conv_id = chat(client, "I need a human")["conversation_id"]
    ticket_id = client.get("/api/tickets").json()[0]["id"]

    client.post(f"/api/tickets/{ticket_id}/reply", json={"content": "Hi, Maya here!", "agent": "Maya"})
    messages = client.get(f"/api/conversations/{conv_id}/messages").json()["messages"]
    assert messages[-1]["role"] == "agent"

    resolved = client.patch(f"/api/tickets/{ticket_id}", json={"status": "resolved"}).json()
    assert resolved["status"] == "resolved"
    assert resolved["first_agent_reply_at"] and resolved["resolved_at"]
    assert client.get(f"/api/conversations/{conv_id}").json()["status"] == "closed"


def test_metrics(client):
    conv_id = chat(client, "What are your store hours?")["conversation_id"]
    client.post(f"/api/conversations/{conv_id}/feedback", json={"helpful": True})
    chat(client, "agent please")

    m = client.get("/api/metrics").json()
    assert m["total_conversations"] == 2
    assert m["automation_rate"] == 0.5
    assert m["csat"] == 1.0
    assert m["open_tickets"] == 1


def test_frustration_escalates_with_high_priority():
    nlu = analyze("This is unacceptable, worst service ever!!")
    result = GenerationResult(answer="...", intent="shipping", confidence=0.9)
    decision = decide_escalation(nlu, result, threshold=0.45, previous_low=False)
    assert decision.escalate and decision.priority == "high"


def test_confident_answer_is_not_escalated():
    nlu = analyze("How much is express shipping?")
    result = GenerationResult(answer="$19.95", intent="shipping", confidence=0.8)
    assert not decide_escalation(nlu, result, threshold=0.45, previous_low=False).escalate
