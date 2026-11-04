import { Bot, Clock, Gauge, Headset, MessagesSquare, Smile, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, INTENT_LABELS } from "../../api";
import { usePolling } from "../../hooks";

// Validated with the dataviz palette checker (CVD-safe pair on white).
const AUTOMATED = "#15803d";
const ESCALATED = "#f59e0b";

const pct = (v: number | null) => (v == null ? "–" : `${Math.round(v * 100)}%`);

function Kpi({ icon: Icon, label, value, hint }: { icon: LucideIcon; label: string; value: string; hint: string }) {
  return (
    <div className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Icon size={16} className="text-brand-700" />
        {label}
      </div>
      <p className="mt-2 text-3xl font-bold tracking-tight text-slate-900">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{hint}</p>
    </div>
  );
}

function HBarList({ title, rows }: { title: string; rows: { label: string; count: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <div className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
      <h3 className="mb-4 text-sm font-semibold text-slate-800">{title}</h3>
      <ul className="space-y-2.5">
        {rows.map((r) => (
          <li key={r.label} className="group" title={`${r.label}: ${r.count}`}>
            <div className="mb-1 flex justify-between text-xs">
              <span className="text-slate-600">{r.label}</span>
              <span className="font-medium text-slate-800 tabular-nums">{r.count}</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100">
              <div
                className="h-2 rounded-full bg-brand-700 transition-all group-hover:bg-brand-900"
                style={{ width: `${(r.count / max) * 100}%` }}
              />
            </div>
          </li>
        ))}
        {!rows.length && <li className="text-sm text-slate-400">No data yet</li>}
      </ul>
    </div>
  );
}

export default function Overview() {
  const [days, setDays] = useState(14);
  const { data: m } = usePolling(() => api.metrics(days), 8000, [days]);

  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Support overview</h1>
          <p className="text-sm text-slate-500">How the AI assistant and the team handled customers. Updates live.</p>
        </div>
        <div className="flex rounded-lg bg-white p-1 text-sm ring-1 ring-slate-200">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`rounded-md px-3 py-1 ${d === days ? "bg-brand-800 font-semibold text-white" : "text-slate-600 hover:bg-slate-50"}`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {!m ? (
        <p className="text-sm text-slate-400">Loading metrics...</p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Kpi icon={MessagesSquare} label="Conversations" value={m.total_conversations.toLocaleString()} hint={`Last ${m.period_days} days`} />
            <Kpi icon={Bot} label="Resolved by AI" value={pct(m.automation_rate)} hint={`${m.automated_conversations} conversations with no human needed`} />
            <Kpi icon={Gauge} label="AI response time" value={`${(m.avg_bot_response_ms / 1000).toFixed(1)}s`} hint={`Average over ${m.bot_messages} answers`} />
            <Kpi icon={Headset} label="Escalation rate" value={pct(m.escalation_rate)} hint={`${m.open_tickets} tickets waiting for the team`} />
            <Kpi
              icon={Clock}
              label="Agent first reply"
              value={m.avg_agent_first_reply_min == null ? "–" : `${Math.round(m.avg_agent_first_reply_min)} min`}
              hint={m.avg_ticket_resolution_min == null ? "No resolved tickets yet" : `${Math.round(m.avg_ticket_resolution_min)} min average time to resolve`}
            />
            <Kpi icon={Smile} label="Customer satisfaction" value={pct(m.csat)} hint={`${m.csat_responses} thumbs-up / thumbs-down ratings`} />
          </div>

          <div className="mt-6 rounded-2xl bg-white p-5 ring-1 ring-slate-200">
            <h3 className="text-sm font-semibold text-slate-800">Conversations per day</h3>
            <p className="mb-4 text-xs text-slate-500">Resolved by the AI assistant vs. handed to a human agent</p>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={m.daily} margin={{ left: -20, right: 8 }}>
                  <CartesianGrid vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(d: string) => new Date(d + "T12:00:00").toLocaleDateString([], { month: "short", day: "numeric" })}
                    tick={{ fontSize: 11, fill: "#64748b" }}
                    tickLine={false}
                    axisLine={{ stroke: "#e2e8f0" }}
                    minTickGap={16}
                  />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} />
                  <Tooltip
                    cursor={{ fill: "#f8fafc" }}
                    labelFormatter={(d: string) => new Date(d + "T12:00:00").toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}
                    contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12 }}
                  />
                  <Legend
                    iconType="circle"
                    iconSize={8}
                    wrapperStyle={{ fontSize: 12 }}
                    formatter={(value: string) => <span style={{ color: "#475569" }}>{value}</span>}
                  />
                  <Bar dataKey="automated" name="Resolved by AI" stackId="a" fill={AUTOMATED} stroke="#fff" strokeWidth={2} maxBarSize={28} />
                  <Bar dataKey="escalated" name="Escalated to agent" stackId="a" fill={ESCALATED} stroke="#fff" strokeWidth={2} radius={[4, 4, 0, 0]} maxBarSize={28} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <HBarList
              title="Top customer intents"
              rows={m.intents.slice(0, 8).map((i) => ({ label: INTENT_LABELS[i.intent] ?? i.intent, count: i.count }))}
            />
            <HBarList title="Why conversations were escalated" rows={m.escalation_reasons.map((r) => ({ label: r.reason, count: r.count }))} />
          </div>
        </>
      )}
    </div>
  );
}
