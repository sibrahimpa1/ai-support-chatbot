import {
  Headset,
  MessageCircle,
  RotateCcw,
  SendHorizontal,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { api, type Message } from "../api";

const STORAGE_KEY = "fernway-chat-conversation";
const QUICK_REPLIES = [
  "Where is my order FW-10234?",
  "How do I return an item?",
  "Do you ship to Canada?",
  "I want to talk to a person",
];

interface ChatMessage extends Message {
  sourceTitles?: string[];
}

const WELCOME: ChatMessage = {
  id: 0,
  conversation_id: "",
  role: "assistant",
  content:
    "Hi! I'm **Fern**, the Fernway Outdoor assistant. Ask me about orders, shipping, returns, billing or gear. I'll bring in a human teammate whenever you need one.",
  intent: "greeting",
  confidence: null,
  response_ms: null,
  sources: [],
  created_at: new Date().toISOString(),
};

function readStoredId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function storeId(id: string | null) {
  try {
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable (private mode, iframe sandbox) */
  }
}

/** Renders the tiny markdown subset the bot uses: **bold** and line breaks. */
function RichText({ text }: { text: string }) {
  return (
    <>
      {text.split("\n").map((line, i) => (
        <Fragment key={i}>
          {i > 0 && <br />}
          {line.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
            part.startsWith("**") && part.endsWith("**") ? (
              <strong key={j} className="font-semibold">
                {part.slice(2, -2)}
              </strong>
            ) : (
              <Fragment key={j}>{part}</Fragment>
            ),
          )}
        </Fragment>
      ))}
    </>
  );
}

interface ChatWidgetProps {
  /** "floating" renders a launcher bubble; "embedded" fills its container (iframe). */
  mode?: "floating" | "embedded";
  defaultOpen?: boolean;
}

export default function ChatWidget({ mode = "floating", defaultOpen = false }: ChatWidgetProps) {
  const [open, setOpen] = useState(defaultOpen || mode === "embedded");
  const [conversationId, setConversationId] = useState<string | null>(readStoredId);
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [escalated, setEscalated] = useState(false);
  const [ticketId, setTicketId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const lastId = messages.reduce((max, m) => Math.max(max, m.id), 0);

  const merge = useCallback((incoming: ChatMessage[]) => {
    setMessages((prev) => {
      const seen = new Set(prev.map((m) => m.id));
      const fresh = incoming.filter((m) => !seen.has(m.id));
      return fresh.length ? [...prev, ...fresh] : prev;
    });
  }, []);

  // Restore an existing conversation after a page reload.
  useEffect(() => {
    if (!conversationId) return;
    api
      .messages(conversationId)
      .then(({ status, messages: history }) => {
        if (history.length) setMessages([WELCOME, ...history]);
        setEscalated(status === "escalated");
      })
      .catch(() => {
        storeId(null);
        setConversationId(null);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // While a human agent owns the chat, poll for their replies.
  useEffect(() => {
    if (!conversationId || !escalated) return;
    const timer = setInterval(async () => {
      try {
        const { status, messages: fresh } = await api.messages(conversationId, lastId);
        merge(fresh);
        if (status === "closed") setEscalated(false);
      } catch {
        /* transient network error: retry on the next tick */
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [conversationId, escalated, lastId, merge]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, typing, open]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || typing) return;
    setInput("");
    setError(null);
    const optimistic: ChatMessage = { ...WELCOME, id: -Date.now(), role: "user", content };
    setMessages((prev) => [...prev, optimistic]);
    setTyping(!escalated);
    try {
      const res = await api.chat(content, conversationId, "Website visitor");
      if (res.conversation_id !== conversationId) {
        setConversationId(res.conversation_id);
        storeId(res.conversation_id);
      }
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      const titles = res.debug?.retrieved
        .filter((r) => res.reply?.sources.includes(r.id))
        .map((r) => r.title);
      merge([res.user_message, ...(res.reply ? [{ ...res.reply, sourceTitles: titles }] : [])]);
      if (res.escalated) setEscalated(true);
      if (res.ticket) setTicketId(res.ticket.id);
    } catch {
      setError("Couldn't reach support. Please try again.");
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      setInput(content);
    } finally {
      setTyping(false);
    }
  }

  async function requestHuman() {
    if (!conversationId) return send("I want to talk to a person");
    const ticket = await api.escalate(conversationId);
    setTicketId(ticket.id);
    setEscalated(true);
    const { messages: fresh } = await api.messages(conversationId, lastId);
    merge(fresh);
  }

  async function rate(helpful: boolean) {
    if (!conversationId) return;
    setFeedback(helpful ? "up" : "down");
    await api.feedback(conversationId, helpful);
  }

  function reset() {
    storeId(null);
    setConversationId(null);
    setMessages([WELCOME]);
    setEscalated(false);
    setTicketId(null);
    setFeedback(null);
  }

  const botReplies = messages.filter((m) => m.role === "assistant" && m.id > 0).length;
  const panel = (
    <div
      className={`flex flex-col overflow-hidden bg-white ${
        mode === "embedded"
          ? "h-full w-full"
          : "pop-in fixed bottom-24 right-4 left-4 h-[min(640px,calc(100vh-8rem))] rounded-2xl shadow-2xl ring-1 ring-black/5 sm:left-auto sm:right-6 sm:w-[390px]"
      }`}
      role="dialog"
      aria-label="Fernway support chat"
    >
      <header className="flex items-center gap-3 bg-brand-900 px-4 py-3.5 text-white">
        <div className="relative">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-700">
            {escalated ? <Headset size={20} /> : <Sparkles size={20} />}
          </div>
          <span className="absolute -right-0.5 -bottom-0.5 h-3 w-3 rounded-full bg-brand-500 ring-2 ring-brand-900" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[15px] leading-tight font-semibold">
            {escalated ? "Fernway Support Team" : "Fern · AI Assistant"}
          </p>
          <p className="text-xs text-brand-200">
            {escalated ? "A specialist will reply here" : "Typically replies instantly"}
          </p>
        </div>
        <button
          onClick={reset}
          className="rounded-lg p-2 text-brand-200 hover:bg-white/10 hover:text-white"
          title="Start a new conversation"
          aria-label="Start a new conversation"
        >
          <RotateCcw size={16} />
        </button>
        {mode === "floating" && (
          <button
            onClick={() => setOpen(false)}
            className="rounded-lg p-2 text-brand-200 hover:bg-white/10 hover:text-white"
            aria-label="Close chat"
          >
            <X size={18} />
          </button>
        )}
      </header>

      {escalated && (
        <div className="flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-900">
          <Headset size={14} className="shrink-0" />
          <span>
            Connected to a human agent{ticketId ? ` · Ticket #${ticketId}` : ""}. You can keep
            typing.
          </span>
        </div>
      )}

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto bg-slate-50 px-4 py-4">
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {typing && (
          <div className="flex items-end gap-2">
            <BotAvatar />
            <div className="flex gap-1 rounded-2xl rounded-bl-sm bg-white px-4 py-3 shadow-sm ring-1 ring-slate-200/70">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="typing-dot h-1.5 w-1.5 rounded-full bg-slate-500"
                  style={{ animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </div>
          </div>
        )}
        {messages.length === 1 && (
          <div className="flex flex-wrap gap-2 pt-1 pl-9">
            {QUICK_REPLIES.map((q) => (
              <button
                key={q}
                onClick={() => send(q)}
                className="rounded-full border border-brand-200 bg-white px-3 py-1.5 text-xs font-medium text-brand-800 hover:border-brand-500 hover:bg-brand-50"
              >
                {q}
              </button>
            ))}
          </div>
        )}
        {botReplies >= 1 && !escalated && !typing && (
          <div className="flex items-center justify-center gap-2 pt-1 text-xs text-slate-500">
            {feedback ? (
              <span>Thanks for the feedback!</span>
            ) : (
              <>
                <span>Was this helpful?</span>
                <button onClick={() => rate(true)} className="rounded-md p-1 hover:bg-white hover:text-brand-700" aria-label="Helpful">
                  <ThumbsUp size={14} />
                </button>
                <button onClick={() => rate(false)} className="rounded-md p-1 hover:bg-white hover:text-red-600" aria-label="Not helpful">
                  <ThumbsDown size={14} />
                </button>
                <span className="text-slate-300">|</span>
                <button onClick={requestHuman} className="font-medium text-brand-700 hover:underline">
                  Talk to a human
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {error && <p className="bg-red-50 px-4 py-2 text-xs text-red-700">{error}</p>}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex items-center gap-2 border-t border-slate-200 bg-white p-3"
      >
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={escalated ? "Message the support team..." : "Ask a question..."}
          className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm outline-none placeholder:text-slate-400 focus:border-brand-500 focus:bg-white focus:ring-2 focus:ring-brand-100"
          maxLength={2000}
          aria-label="Message"
        />
        <button
          type="submit"
          disabled={!input.trim() || typing}
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-700 text-white transition hover:bg-brand-800 disabled:opacity-40"
          aria-label="Send"
        >
          <SendHorizontal size={18} />
        </button>
      </form>
      <p className="bg-white pb-2 text-center text-[10px] text-slate-400">
        AI answers are grounded in the Fernway help center
      </p>
    </div>
  );

  if (mode === "embedded") return panel;
  return (
    <>
      {open && panel}
      <button
        onClick={() => setOpen((o) => !o)}
        className="fixed right-4 bottom-4 flex h-14 w-14 items-center justify-center rounded-full bg-brand-800 text-white shadow-xl transition hover:scale-105 hover:bg-brand-900 sm:right-6 sm:bottom-6"
        aria-label={open ? "Close chat" : "Open chat"}
      >
        {open ? <X size={24} /> : <MessageCircle size={26} />}
      </button>
    </>
  );
}

function BotAvatar() {
  return (
    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-100 text-brand-800">
      <Sparkles size={14} />
    </div>
  );
}

function MessageBubble({ message: m }: { message: ChatMessage }) {
  if (m.role === "system") {
    return <p className="py-1 text-center text-xs text-slate-500">{m.content}</p>;
  }
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-brand-700 px-3.5 py-2.5 text-sm text-white">
          {m.content}
        </div>
      </div>
    );
  }
  const isAgent = m.role === "agent";
  return (
    <div className="flex items-end gap-2">
      {isAgent ? (
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-800">
          <Headset size={14} />
        </div>
      ) : (
        <BotAvatar />
      )}
      <div className="max-w-[80%]">
        {isAgent && <p className="mb-1 text-[11px] font-medium text-amber-700">Support agent</p>}
        <div className="rounded-2xl rounded-bl-sm bg-white px-3.5 py-2.5 text-sm leading-relaxed text-slate-700 shadow-sm ring-1 ring-slate-200/70">
          <RichText text={m.content} />
        </div>
        {!!m.sourceTitles?.length && (
          <p className="mt-1 text-[11px] text-slate-400">Source: {m.sourceTitles.join(", ")}</p>
        )}
      </div>
    </div>
  );
}
