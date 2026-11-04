import type { Conversation, Ticket } from "../api";

const PRIORITY: Record<Ticket["priority"], string> = {
  urgent: "bg-red-600 text-white",
  high: "bg-red-50 text-red-700 ring-1 ring-red-200",
  normal: "bg-slate-100 text-slate-700",
  low: "bg-slate-50 text-slate-500",
};

const TICKET_STATUS: Record<Ticket["status"], [string, string]> = {
  open: ["Open", "bg-amber-50 text-amber-800 ring-1 ring-amber-200"],
  in_progress: ["In progress", "bg-sky-50 text-sky-800 ring-1 ring-sky-200"],
  resolved: ["Resolved", "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"],
};

const CONV_STATUS: Record<Conversation["status"], [string, string]> = {
  bot_active: ["Bot active", "bg-brand-50 text-brand-800"],
  resolved: ["Resolved by AI", "bg-emerald-50 text-emerald-700"],
  escalated: ["With agent", "bg-amber-50 text-amber-800"],
  closed: ["Closed by agent", "bg-slate-100 text-slate-600"],
};

const base = "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap";

export const PriorityBadge = ({ value }: { value: Ticket["priority"] }) => (
  <span className={`${base} capitalize ${PRIORITY[value]}`}>{value}</span>
);

export const TicketStatusBadge = ({ value }: { value: Ticket["status"] }) => (
  <span className={`${base} ${TICKET_STATUS[value][1]}`}>{TICKET_STATUS[value][0]}</span>
);

export const ConversationStatusBadge = ({ value }: { value: Conversation["status"] }) => (
  <span className={`${base} ${CONV_STATUS[value][1]}`}>{CONV_STATUS[value][0]}</span>
);
