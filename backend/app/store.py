"""SQLite persistence for conversations, messages and escalation tickets.

Plain `sqlite3` keeps the demo dependency-free. The `Store` methods are the
only place SQL lives, so moving to Postgres means reimplementing this class.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    customer_email TEXT,
    status TEXT NOT NULL DEFAULT 'bot_active',  -- bot_active | resolved | escalated | closed
    intent TEXT,
    csat INTEGER,                               -- 1 (thumbs down) or 5 (thumbs up)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,                          -- user | assistant | agent | system
    content TEXT NOT NULL,
    intent TEXT,
    confidence REAL,
    response_ms INTEGER,
    sources TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    status TEXT NOT NULL DEFAULT 'open',         -- open | in_progress | resolved
    priority TEXT NOT NULL DEFAULT 'normal',     -- low | normal | high | urgent
    category TEXT,
    reason TEXT NOT NULL,
    summary TEXT NOT NULL,
    assignee TEXT,
    created_at TEXT NOT NULL,
    first_agent_reply_at TEXT,
    resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
CREATE INDEX IF NOT EXISTS idx_tickets_conv ON tickets(conversation_id);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._batching = False
        with self._lock:
            self._conn.executescript(SCHEMA)

    def _query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def _execute(self, sql: str, params: tuple = ()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, params)
            if not self._batching:
                self._conn.commit()
            return cur.lastrowid or 0

    @contextmanager
    def batch(self):
        """Run many writes in one transaction (used for bulk seeding)."""
        with self._lock:
            self._batching = True
            try:
                yield self
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
            finally:
                self._batching = False

    # Conversations ---------------------------------------------------------

    def create_conversation(
        self, customer_name: str, customer_email: str | None = None, at: datetime | None = None
    ) -> dict[str, Any]:
        conv_id = uuid.uuid4().hex[:12]
        ts = iso(at or utcnow())
        self._execute(
            "INSERT INTO conversations (id, customer_name, customer_email, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (conv_id, customer_name, customer_email, ts, ts),
        )
        return self.get_conversation(conv_id)  # type: ignore[return-value]

    def get_conversation(self, conv_id: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM conversations WHERE id = ?", (conv_id,))
        return rows[0] if rows else None

    def update_conversation(self, conv_id: str, at: datetime | None = None, **fields: Any) -> None:
        fields["updated_at"] = iso(at or utcnow())
        cols = ", ".join(f"{k} = ?" for k in fields)
        self._execute(f"UPDATE conversations SET {cols} WHERE id = ?", (*fields.values(), conv_id))

    def list_conversations(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        sql = """
            SELECT c.*,
                   (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count,
                   (SELECT content FROM messages m WHERE m.conversation_id = c.id
                     ORDER BY m.id DESC LIMIT 1) AS last_message,
                   (SELECT id FROM tickets t WHERE t.conversation_id = c.id
                     ORDER BY t.id DESC LIMIT 1) AS ticket_id
            FROM conversations c
        """
        params: tuple = ()
        if status:
            sql += " WHERE c.status = ?"
            params = (status,)
        sql += " ORDER BY c.updated_at DESC LIMIT ?"
        return self._query(sql, (*params, limit))

    # Messages --------------------------------------------------------------

    def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        *,
        intent: str | None = None,
        confidence: float | None = None,
        response_ms: int | None = None,
        sources: list[str] | None = None,
        at: datetime | None = None,
    ) -> dict[str, Any]:
        ts = at or utcnow()
        msg_id = self._execute(
            "INSERT INTO messages (conversation_id, role, content, intent, confidence,"
            " response_ms, sources, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (conv_id, role, content, intent, confidence, response_ms,
             json.dumps(sources or []), iso(ts)),
        )
        self.update_conversation(conv_id, at=ts)
        return self._query("SELECT * FROM messages WHERE id = ?", (msg_id,))[0] | {
            "sources": sources or []
        }

    def get_messages(self, conv_id: str, after_id: int = 0) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT * FROM messages WHERE conversation_id = ? AND id > ? ORDER BY id",
            (conv_id, after_id),
        )
        for r in rows:
            r["sources"] = json.loads(r["sources"] or "[]")
        return rows

    # Tickets ---------------------------------------------------------------

    def create_ticket(
        self,
        conv_id: str,
        *,
        reason: str,
        summary: str,
        priority: str = "normal",
        category: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, Any]:
        ticket_id = self._execute(
            "INSERT INTO tickets (conversation_id, priority, category, reason, summary, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (conv_id, priority, category, reason, summary, iso(at or utcnow())),
        )
        return self.get_ticket(ticket_id)  # type: ignore[return-value]

    def get_ticket(self, ticket_id: int) -> dict[str, Any] | None:
        rows = self._query(
            "SELECT t.*, c.customer_name, c.customer_email FROM tickets t"
            " JOIN conversations c ON c.id = t.conversation_id WHERE t.id = ?",
            (ticket_id,),
        )
        return rows[0] if rows else None

    def open_ticket_for(self, conv_id: str) -> dict[str, Any] | None:
        rows = self._query(
            "SELECT id FROM tickets WHERE conversation_id = ? AND status != 'resolved'"
            " ORDER BY id DESC LIMIT 1",
            (conv_id,),
        )
        return self.get_ticket(rows[0]["id"]) if rows else None

    def list_tickets(self, status: str | None = None) -> list[dict[str, Any]]:
        sql = (
            "SELECT t.*, c.customer_name, c.customer_email FROM tickets t"
            " JOIN conversations c ON c.id = t.conversation_id"
        )
        params: tuple = ()
        if status:
            sql += " WHERE t.status = ?"
            params = (status,)
        sql += """ ORDER BY CASE t.status WHEN 'open' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END,
                   CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1
                                   WHEN 'normal' THEN 2 ELSE 3 END,
                   t.created_at DESC"""
        return self._query(sql, params)

    def update_ticket(self, ticket_id: int, **fields: Any) -> None:
        cols = ", ".join(f"{k} = ?" for k in fields)
        self._execute(f"UPDATE tickets SET {cols} WHERE id = ?", (*fields.values(), ticket_id))

    # Metrics ---------------------------------------------------------------

    def metrics(self, days: int = 14) -> dict[str, Any]:
        since = iso(utcnow() - timedelta(days=days))
        convs = self._query("SELECT * FROM conversations WHERE created_at >= ?", (since,))
        total = len(convs)
        escalated_ids = {
            r["conversation_id"]
            for r in self._query(
                "SELECT DISTINCT conversation_id FROM tickets WHERE created_at >= ?", (since,)
            )
        }
        automated = total - len(escalated_ids)

        bot = self._query(
            "SELECT AVG(response_ms) AS avg_ms, COUNT(*) AS n FROM messages"
            " WHERE role = 'assistant' AND response_ms IS NOT NULL AND created_at >= ?",
            (since,),
        )[0]
        tickets = self._query("SELECT * FROM tickets WHERE created_at >= ?", (since,))

        def minutes(start: str, end: str | None) -> float | None:
            if not end:
                return None
            delta = datetime.fromisoformat(end) - datetime.fromisoformat(start)
            return delta.total_seconds() / 60

        first_reply = [m for t in tickets if (m := minutes(t["created_at"], t["first_agent_reply_at"]))]
        resolution = [m for t in tickets if (m := minutes(t["created_at"], t["resolved_at"]))]
        rated = [c["csat"] for c in convs if c["csat"] is not None]

        daily: dict[str, dict[str, Any]] = {}
        for i in range(days - 1, -1, -1):
            day = (utcnow() - timedelta(days=i)).date().isoformat()
            daily[day] = {"date": day, "automated": 0, "escalated": 0}
        for c in convs:
            day = c["created_at"][:10]
            if day in daily:
                daily[day]["escalated" if c["id"] in escalated_ids else "automated"] += 1

        intents: dict[str, int] = {}
        for c in convs:
            if c["intent"]:
                intents[c["intent"]] = intents.get(c["intent"], 0) + 1

        reasons: dict[str, int] = {}
        for t in tickets:
            key = t["reason"].split(" (")[0]
            reasons[key] = reasons.get(key, 0) + 1

        return {
            "period_days": days,
            "total_conversations": total,
            "automated_conversations": automated,
            "escalated_conversations": len(escalated_ids),
            "automation_rate": round(automated / total, 3) if total else 0.0,
            "escalation_rate": round(len(escalated_ids) / total, 3) if total else 0.0,
            "avg_bot_response_ms": round(bot["avg_ms"] or 0),
            "bot_messages": bot["n"],
            "open_tickets": sum(1 for t in tickets if t["status"] != "resolved"),
            "avg_agent_first_reply_min": round(sum(first_reply) / len(first_reply), 1)
            if first_reply else None,
            "avg_ticket_resolution_min": round(sum(resolution) / len(resolution), 1)
            if resolution else None,
            "csat": round(sum(1 for r in rated if r >= 4) / len(rated), 3) if rated else None,
            "csat_responses": len(rated),
            "daily": list(daily.values()),
            "intents": sorted(
                ({"intent": k, "count": v} for k, v in intents.items()),
                key=lambda x: x["count"], reverse=True,
            ),
            "escalation_reasons": sorted(
                ({"reason": k, "count": v} for k, v in reasons.items()),
                key=lambda x: x["count"], reverse=True,
            ),
        }

    def count_conversations(self) -> int:
        return self._query("SELECT COUNT(*) AS n FROM conversations")[0]["n"]
