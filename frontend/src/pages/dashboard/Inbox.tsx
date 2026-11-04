import { AlertTriangle, CheckCircle2, Inbox as InboxIcon, SendHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, INTENT_LABELS, timeAgo, type Ticket } from "../../api";
import { PriorityBadge, TicketStatusBadge } from "../../components/Badges";
import Transcript from "../../components/Transcript";
import { usePolling } from "../../hooks";

const AGENT = "Maya (Tier 1)";
const FILTERS = [
  { key: "active", label: "Active" },
  { key: "resolved", label: "Resolved" },
  { key: "all", label: "All" },
] as const;

export default function Inbox() {
  const { ticketId } = useParams();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("active");
  const { data: tickets, refresh } = usePolling(api.tickets, 4000);

  const visible = (tickets ?? []).filter((t) =>
    filter === "all" ? true : filter === "resolved" ? t.status === "resolved" : t.status !== "resolved",
  );
  const selected = tickets?.find((t) => String(t.id) === ticketId);

  // Pin the default selection in the URL. Otherwise a list refresh could swap the
  // ticket under an agent mid-reply when priorities or statuses change.
  useEffect(() => {
    if (!ticketId && visible[0]) navigate(`/dashboard/inbox/${visible[0].id}`, { replace: true });
  }, [ticketId, visible, navigate]);

  return (
    <div className="flex h-full min-h-[calc(100vh-0px)] flex-col lg:flex-row">
      <section className="border-slate-200 bg-white lg:w-96 lg:shrink-0 lg:border-r">
        <div className="border-b border-slate-200 p-4">
          <h1 className="text-lg font-bold text-slate-900">Escalations</h1>
          <p className="text-xs text-slate-500">Conversations the AI handed to the team, highest priority first</p>
          <div className="mt-3 flex gap-1 text-sm">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`rounded-md px-2.5 py-1 ${filter === f.key ? "bg-slate-900 font-medium text-white" : "text-slate-600 hover:bg-slate-100"}`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
        <ul className="max-h-[40vh] divide-y divide-slate-100 overflow-y-auto lg:max-h-[calc(100vh-120px)]">
          {visible.map((t) => (
            <li key={t.id}>
              <Link
                to={`/dashboard/inbox/${t.id}`}
                className={`block px-4 py-3 hover:bg-slate-50 ${selected?.id === t.id ? "bg-brand-50/70" : ""}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold text-slate-800">
                    #{t.id} · {t.customer_name}
                  </span>
                  <span className="shrink-0 text-[11px] text-slate-400">{timeAgo(t.created_at)}</span>
                </div>
                <p className="mt-0.5 truncate text-xs text-slate-500">{t.reason}</p>
                <div className="mt-1.5 flex gap-1.5">
                  <PriorityBadge value={t.priority} />
                  <TicketStatusBadge value={t.status} />
                  {t.category && (
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
                      {INTENT_LABELS[t.category] ?? t.category}
                    </span>
                  )}
                </div>
              </Link>
            </li>
          ))}
          {tickets && !visible.length && (
            <li className="flex flex-col items-center gap-2 p-10 text-center text-sm text-slate-400">
              <InboxIcon size={28} />
              Nothing here. The AI is handling everything.
            </li>
          )}
        </ul>
      </section>

      <section className="min-w-0 flex-1">
        {selected ? (
          <TicketDetail key={selected.id} ticket={selected} onChange={refresh} onResolved={() => navigate("/dashboard/inbox")} />
        ) : (
          <p className="p-10 text-sm text-slate-400">Select a ticket</p>
        )}
      </section>
    </div>
  );
}

function TicketDetail({ ticket, onChange, onResolved }: { ticket: Ticket; onChange: () => void; onResolved: () => void }) {
  const [draft, setDraft] = useState("");
  const { data: conv, refresh } = usePolling(() => api.conversation(ticket.conversation_id), 3000, [ticket.conversation_id]);

  async function send() {
    if (!draft.trim()) return;
    await api.reply(ticket.id, draft.trim(), AGENT);
    setDraft("");
    refresh();
    onChange();
  }

  async function resolve() {
    await api.updateTicket(ticket.id, { status: "resolved" });
    onChange();
    onResolved();
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 bg-white p-4 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              Ticket #{ticket.id} · {ticket.customer_name}
            </h2>
            <p className="text-xs text-slate-500">
              {ticket.customer_email ?? "Website visitor"} · opened {timeAgo(ticket.created_at)}
              {ticket.assignee ? ` · assigned to ${ticket.assignee}` : " · unassigned"}
            </p>
          </div>
          {ticket.status !== "resolved" && (
            <button
              onClick={resolve}
              className="flex items-center gap-1.5 rounded-lg bg-brand-800 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-900"
            >
              <CheckCircle2 size={16} /> Mark resolved
            </button>
          )}
        </div>
        <div className="mt-3 flex gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">Escalation reason: {ticket.reason}</p>
            <p className="mt-0.5 text-xs text-amber-800">{ticket.summary}</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 sm:px-6">
        {conv ? <Transcript messages={conv.messages} /> : <p className="text-sm text-slate-400">Loading...</p>}
      </div>

      {ticket.status !== "resolved" && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
          className="flex gap-2 border-t border-slate-200 bg-white p-4 sm:px-6"
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={`Reply to ${ticket.customer_name} as ${AGENT}...`}
            className="flex-1 rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
          />
          <button
            type="submit"
            disabled={!draft.trim()}
            className="flex items-center gap-1.5 rounded-xl bg-brand-700 px-4 text-sm font-semibold text-white hover:bg-brand-800 disabled:opacity-40"
          >
            <SendHorizontal size={16} /> Send
          </button>
        </form>
      )}
    </div>
  );
}
