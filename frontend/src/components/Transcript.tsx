import { Bot, Headset, User } from "lucide-react";
import { INTENT_LABELS, type Message } from "../api";

function ConfidencePill({ value }: { value: number }) {
  const tone =
    value >= 0.7 ? "bg-emerald-50 text-emerald-700" : value >= 0.45 ? "bg-amber-50 text-amber-700" : "bg-red-50 text-red-700";
  return <span className={`rounded px-1.5 py-0.5 font-medium ${tone}`}>{Math.round(value * 100)}% conf.</span>;
}

/** Full conversation history with the bot's NLU metadata, as agents see it. */
export default function Transcript({ messages }: { messages: Message[] }) {
  return (
    <div className="space-y-4">
      {messages.map((m) => {
        if (m.role === "system") {
          return (
            <p key={m.id} className="text-center text-xs text-slate-400">
              {m.content}
            </p>
          );
        }
        const meta = {
          user: { icon: User, label: "Customer", tone: "bg-slate-100 text-slate-600" },
          assistant: { icon: Bot, label: "AI assistant", tone: "bg-brand-100 text-brand-800" },
          agent: { icon: Headset, label: "Agent", tone: "bg-amber-100 text-amber-800" },
        }[m.role];
        const Icon = meta.icon;
        return (
          <div key={m.id} className="flex gap-3">
            <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${meta.tone}`}>
              <Icon size={15} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span className="font-semibold text-slate-700">{meta.label}</span>
                <span>{new Date(m.created_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}</span>
                {m.role === "assistant" && m.intent && (
                  <span className="rounded bg-slate-100 px-1.5 py-0.5">{INTENT_LABELS[m.intent] ?? m.intent}</span>
                )}
                {m.role === "assistant" && m.confidence != null && <ConfidencePill value={m.confidence} />}
                {m.response_ms != null && <span>{(m.response_ms / 1000).toFixed(2)}s</span>}
              </div>
              <p className="mt-1 text-sm leading-relaxed whitespace-pre-line text-slate-700">
                {m.content.replace(/\*\*/g, "")}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
