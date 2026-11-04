"""FastAPI application: chat API for the widget and REST API for the support dashboard."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import BASE_DIR, Settings, get_settings
from app.engine import SupportEngine
from app.knowledge_base import HybridRetriever
from app.providers import build_provider
from app.seed import seed_demo_data
from app.store import Store, iso, utcnow

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    customer_name: str = Field(default="Guest", max_length=80)
    customer_email: str | None = Field(default=None, max_length=120)


class FeedbackRequest(BaseModel):
    helpful: bool


class TicketUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved"] | None = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    assignee: str | None = None


class AgentReply(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    agent: str = "Support Agent"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = Store(settings.database_path)
        if settings.seed_demo_data:
            seed_demo_data(store)
        provider = build_provider(settings)
        app.state.store = store
        app.state.engine = SupportEngine(settings, store, provider)
        logging.getLogger("app").info("LLM provider: %s", provider.name)
        yield

    app = FastAPI(title="AI Support Chatbot API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def store() -> Store:
        return app.state.store

    def engine() -> SupportEngine:
        return app.state.engine

    def conversation_or_404(conv_id: str) -> dict:
        conv = store().get_conversation(conv_id)
        if conv is None:
            raise HTTPException(404, "Conversation not found")
        return conv

    def ticket_or_404(ticket_id: int) -> dict:
        ticket = store().get_ticket(ticket_id)
        if ticket is None:
            raise HTTPException(404, "Ticket not found")
        return ticket

    # Widget ---------------------------------------------------------------

    @app.get("/api/health")
    def health():
        provider = engine().provider
        return {
            "status": "ok",
            "company": settings.company_name,
            "provider": provider.name,
            "model": getattr(provider, "model", None),
            "knowledge_base_chunks": len(engine().retriever.chunks),
            "nlu": "trained classifier" if engine().classifier else "rules",
            "retrieval": "embeddings" if isinstance(engine().retriever, HybridRetriever) else "bm25",
        }

    @app.post("/api/chat")
    def chat(body: ChatRequest):
        return engine().handle_message(
            body.message.strip(), body.conversation_id, body.customer_name, body.customer_email
        )

    @app.get("/api/conversations/{conv_id}/messages")
    def conversation_messages(conv_id: str, after: int = 0):
        conv = conversation_or_404(conv_id)
        return {"status": conv["status"], "messages": store().get_messages(conv_id, after)}

    @app.post("/api/conversations/{conv_id}/escalate")
    def escalate(conv_id: str):
        conversation_or_404(conv_id)
        return engine().escalate_manually(conv_id)

    @app.post("/api/conversations/{conv_id}/feedback")
    def feedback(conv_id: str, body: FeedbackRequest):
        conv = conversation_or_404(conv_id)
        fields: dict = {"csat": 5 if body.helpful else 1}
        if body.helpful and conv["status"] == "bot_active":
            fields["status"] = "resolved"
        store().update_conversation(conv_id, **fields)
        return store().get_conversation(conv_id)

    # Dashboard ------------------------------------------------------------

    @app.get("/api/conversations")
    def conversations(status: str | None = None, limit: int = Query(50, le=500)):
        return store().list_conversations(status, limit)

    @app.get("/api/conversations/{conv_id}")
    def conversation(conv_id: str):
        conv = conversation_or_404(conv_id)
        tickets = [t for t in store().list_tickets() if t["conversation_id"] == conv_id]
        return conv | {"messages": store().get_messages(conv_id), "tickets": tickets}

    @app.get("/api/tickets")
    def tickets(status: str | None = None):
        return store().list_tickets(status)

    @app.patch("/api/tickets/{ticket_id}")
    def update_ticket(ticket_id: int, body: TicketUpdate):
        ticket = ticket_or_404(ticket_id)
        fields = body.model_dump(exclude_none=True)
        if fields.get("status") == "resolved":
            fields["resolved_at"] = iso(utcnow())
            store().update_conversation(ticket["conversation_id"], status="closed")
            store().add_message(ticket["conversation_id"], "system", "The support team marked this conversation as resolved.")
        if fields:
            store().update_ticket(ticket_id, **fields)
        return store().get_ticket(ticket_id)

    @app.post("/api/tickets/{ticket_id}/reply")
    def reply(ticket_id: int, body: AgentReply):
        ticket = ticket_or_404(ticket_id)
        message = store().add_message(ticket["conversation_id"], "agent", body.content)
        fields: dict = {}
        if not ticket["first_agent_reply_at"]:
            fields["first_agent_reply_at"] = message["created_at"]
        if ticket["status"] == "open":
            fields |= {"status": "in_progress", "assignee": ticket["assignee"] or body.agent}
        if fields:
            store().update_ticket(ticket_id, **fields)
        return message

    @app.get("/api/metrics")
    def metrics(days: int = Query(14, ge=1, le=90)):
        return store().metrics(days)

    @app.get("/api/model-quality")
    def model_quality():
        """Latest offline evaluation report (generated by `make eval`)."""
        path = BASE_DIR / "eval" / "results.json"
        if not path.exists():
            raise HTTPException(404, "No evaluation report yet. Run `make eval`.")
        return json.loads(path.read_text())

    @app.get("/api/knowledge-base")
    def knowledge_base(q: str | None = None):
        if q:
            return [
                {"id": r.chunk.id, "source": r.chunk.source, "title": r.chunk.title,
                 "text": r.chunk.text, "score": round(r.score, 2)}
                for r in engine().retriever.search(q, 8)
            ]
        return [c.__dict__ for c in engine().retriever.chunks]

    # Built frontend (docker / production): serve the SPA from the same origin.
    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            file = (FRONTEND_DIST / path).resolve()
            if path and file.is_file() and FRONTEND_DIST.resolve() in file.parents:
                return FileResponse(file)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
