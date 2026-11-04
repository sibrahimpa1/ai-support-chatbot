import { X } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, INTENT_LABELS, timeAgo } from "../../api";
import { ConversationStatusBadge } from "../../components/Badges";
import Transcript from "../../components/Transcript";
import { usePolling } from "../../hooks";

const STATUSES = [
  { key: "", label: "All" },
  { key: "bot_active", label: "Bot active" },
  { key: "resolved", label: "Resolved by AI" },
  { key: "escalated", label: "With agent" },
  { key: "closed", label: "Closed" },
];

export default function Conversations() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState("");
  const { data: rows } = usePolling(() => api.conversations(status || undefined), 6000, [status]);

  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-8">
      <h1 className="text-2xl font-bold text-slate-900">Conversations</h1>
      <p className="text-sm text-slate-500">Every chat, with the intent the AI detected and how it ended.</p>

      <div className="mt-5 mb-4 flex flex-wrap gap-1 text-sm">
        {STATUSES.map((s) => (
          <button
            key={s.key}
            onClick={() => setStatus(s.key)}
            className={`rounded-md px-3 py-1 ${status === s.key ? "bg-slate-900 font-medium text-white" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"}`}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto rounded-2xl bg-white ring-1 ring-slate-200">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-slate-200 text-xs text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Customer</th>
              <th className="px-4 py-3 font-medium">Last message</th>
              <th className="px-4 py-3 font-medium">Intent</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Rating</th>
              <th className="px-4 py-3 text-right font-medium">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows?.map((c) => (
              <tr key={c.id} className="cursor-pointer hover:bg-slate-50" onClick={() => navigate(`/dashboard/conversations/${c.id}`)}>
                <td className="px-4 py-3 font-medium whitespace-nowrap text-slate-800">{c.customer_name}</td>
                <td className="max-w-xs truncate px-4 py-3 text-slate-500">{c.last_message?.replace(/\*\*/g, "")}</td>
                <td className="px-4 py-3 whitespace-nowrap text-slate-600">{c.intent ? INTENT_LABELS[c.intent] ?? c.intent : "–"}</td>
                <td className="px-4 py-3"><ConversationStatusBadge value={c.status} /></td>
                <td className="px-4 py-3 text-slate-600">{c.csat == null ? "–" : c.csat >= 4 ? "👍" : "👎"}</td>
                <td className="px-4 py-3 text-right whitespace-nowrap text-slate-400">{timeAgo(c.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows && !rows.length && <p className="p-8 text-center text-sm text-slate-400">No conversations</p>}
      </div>

      {conversationId && <ConversationDrawer id={conversationId} />}
    </div>
  );
}

function ConversationDrawer({ id }: { id: string }) {
  const { data: conv } = usePolling(() => api.conversation(id), 4000, [id]);
  const ticket = conv?.tickets[0];
  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-slate-900/30" onClick={(e) => e.target === e.currentTarget && history.back()}>
      <div className="flex h-full w-full max-w-xl flex-col bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-slate-200 p-5">
          <div>
            <h2 className="text-lg font-bold text-slate-900">{conv?.customer_name ?? "..."}</h2>
            {conv && (
              <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                <ConversationStatusBadge value={conv.status} />
                started {timeAgo(conv.created_at)}
                {ticket && (
                  <Link to={`/dashboard/inbox/${ticket.id}`} className="font-medium text-brand-700 hover:underline">
                    Ticket #{ticket.id}
                  </Link>
                )}
              </div>
            )}
          </div>
          <Link to="/dashboard/conversations" className="rounded-lg p-2 text-slate-400 hover:bg-slate-100" aria-label="Close">
            <X size={18} />
          </Link>
        </div>
        <div className="flex-1 overflow-y-auto p-5">{conv && <Transcript messages={conv.messages} />}</div>
      </div>
    </div>
  );
}
