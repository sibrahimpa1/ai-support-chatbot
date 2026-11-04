export type Role = "user" | "assistant" | "agent" | "system";

export interface Message {
  id: number;
  conversation_id: string;
  role: Role;
  content: string;
  intent: string | null;
  confidence: number | null;
  response_ms: number | null;
  sources: string[];
  created_at: string;
}

export interface Ticket {
  id: number;
  conversation_id: string;
  status: "open" | "in_progress" | "resolved";
  priority: "low" | "normal" | "high" | "urgent";
  category: string | null;
  reason: string;
  summary: string;
  assignee: string | null;
  created_at: string;
  first_agent_reply_at: string | null;
  resolved_at: string | null;
  customer_name: string;
  customer_email: string | null;
}

export interface Conversation {
  id: string;
  customer_name: string;
  customer_email: string | null;
  status: "bot_active" | "resolved" | "escalated" | "closed";
  intent: string | null;
  csat: number | null;
  created_at: string;
  updated_at: string;
  message_count?: number;
  last_message?: string;
  ticket_id?: number | null;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
  tickets: Ticket[];
}

export interface ChatResponse {
  conversation_id: string;
  user_message: Message;
  reply: Message | null;
  escalated: boolean;
  ticket: Ticket | null;
  provider: string;
  debug: {
    nlu_intent: string;
    nlu_confidence: number;
    sentiment: number;
    escalation_reason: string | null;
    retrieved: { id: string; title: string; score: number }[];
  } | null;
}

export interface Metrics {
  period_days: number;
  total_conversations: number;
  automated_conversations: number;
  escalated_conversations: number;
  automation_rate: number;
  escalation_rate: number;
  avg_bot_response_ms: number;
  bot_messages: number;
  open_tickets: number;
  avg_agent_first_reply_min: number | null;
  avg_ticket_resolution_min: number | null;
  csat: number | null;
  csat_responses: number;
  daily: { date: string; automated: number; escalated: number }[];
  intents: { intent: string; count: number }[];
  escalation_reasons: { reason: string; count: number }[];
}

export interface Health {
  status: string;
  company: string;
  provider: string;
  model: string | null;
  knowledge_base_chunks: number;
}

export interface KbArticle {
  id: string;
  source: string;
  title: string;
  text: string;
  score?: number;
}

// Same-origin by default (Vite proxy in dev, FastAPI serves the build in prod).
const BASE = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });

export const api = {
  health: () => request<Health>("/api/health"),
  chat: (message: string, conversation_id?: string | null, customer_name?: string) =>
    post<ChatResponse>("/api/chat", { message, conversation_id, customer_name }),
  messages: (id: string, after = 0) =>
    request<{ status: Conversation["status"]; messages: Message[] }>(
      `/api/conversations/${id}/messages?after=${after}`,
    ),
  escalate: (id: string) => post<Ticket>(`/api/conversations/${id}/escalate`),
  feedback: (id: string, helpful: boolean) =>
    post<Conversation>(`/api/conversations/${id}/feedback`, { helpful }),
  conversations: (status?: string) =>
    request<Conversation[]>(`/api/conversations?limit=200${status ? `&status=${status}` : ""}`),
  conversation: (id: string) => request<ConversationDetail>(`/api/conversations/${id}`),
  tickets: () => request<Ticket[]>("/api/tickets"),
  updateTicket: (id: number, body: Partial<Pick<Ticket, "status" | "priority" | "assignee">>) =>
    request<Ticket>(`/api/tickets/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  reply: (id: number, content: string, agent: string) =>
    post<Message>(`/api/tickets/${id}/reply`, { content, agent }),
  metrics: (days = 14) => request<Metrics>(`/api/metrics?days=${days}`),
  knowledgeBase: (q?: string) =>
    request<KbArticle[]>(`/api/knowledge-base${q ? `?q=${encodeURIComponent(q)}` : ""}`),
};

export const INTENT_LABELS: Record<string, string> = {
  greeting: "Greeting",
  order_status: "Order status",
  order_change: "Order change",
  shipping: "Shipping",
  returns_refunds: "Returns & refunds",
  billing: "Billing",
  account: "Account",
  product_info: "Product info",
  store_info: "Store info",
  human_handoff: "Human handoff",
  complaint: "Complaint",
  thanks: "Thanks",
  other: "Other",
};

export function timeAgo(iso: string): string {
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}
