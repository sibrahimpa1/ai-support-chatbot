import { ArrowUpRight, FlaskConical } from "lucide-react";
import { useEffect, useState } from "react";
import { api, INTENT_LABELS, type ModelQuality as Report } from "../../api";

const BASELINE = "Baseline: regex rules + BM25";
const CURRENT = "Current: ML intents + embedding retrieval";
const PRODUCTION_INTENT = "ML: embeddings";
const PRODUCTION_RETRIEVAL = "Embeddings + intent boost";

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const points = (a: number, b: number) => `${b >= a ? "+" : ""}${((b - a) * 100).toFixed(1)} pts`;

function Delta({ label, before, after, hint }: { label: string; before: number; after: number; hint: string }) {
  return (
    <div className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
      <p className="text-sm text-slate-500">{label}</p>
      <div className="mt-2 flex items-baseline gap-2">
        <p className="text-3xl font-bold tracking-tight text-slate-900">{pct(after)}</p>
        <span className="flex items-center text-xs font-semibold text-brand-700">
          <ArrowUpRight size={14} />
          {points(before, after)}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {hint}: was {pct(before)}
      </p>
    </div>
  );
}

/** One bar per method; the configuration running in production is highlighted. */
function MethodBars({ rows, production }: { rows: { name: string; value: number; detail: string }[]; production: string }) {
  return (
    <ul className="space-y-3">
      {rows.map((r) => {
        const live = r.name === production;
        return (
          <li key={r.name} title={`${r.name}: ${pct(r.value)}`}>
            <div className="mb-1 flex items-center justify-between gap-3 text-xs">
              <span className={live ? "font-semibold text-slate-900" : "text-slate-600"}>
                {r.name}
                {live && <span className="ml-2 rounded bg-brand-100 px-1.5 py-0.5 text-[10px] font-semibold text-brand-800">IN PRODUCTION</span>}
              </span>
              <span className="text-slate-500 tabular-nums">{r.detail}</span>
            </div>
            <div className="h-2.5 rounded-full bg-slate-100">
              <div
                className={`h-2.5 rounded-full ${live ? "bg-brand-700" : "bg-slate-400"}`}
                style={{ width: `${r.value * 100}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export default function ModelQuality() {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.modelQuality().then(setReport).catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <div className="p-8 text-sm text-slate-500">
        No evaluation report yet. Run <code className="rounded bg-slate-100 px-1.5 py-0.5">make eval</code>.
      </div>
    );
  }
  if (!report) return <p className="p-8 text-sm text-slate-400">Loading evaluation...</p>;

  const base = report.escalation[BASELINE];
  const now = report.escalation[CURRENT];
  const intentBase = report.intents["Regex rules (baseline)"].accuracy;
  const intentNow = report.intents[PRODUCTION_INTENT].accuracy;
  const retrievalBase = report.retrieval["BM25 (baseline)"].recall_at_3;
  const retrievalNow = report.retrieval[PRODUCTION_RETRIEVAL].recall_at_3;

  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-8">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
          <FlaskConical size={22} className="text-brand-700" /> Model quality
        </h1>
        <p className="text-sm text-slate-500">
          Measured on {report.n_cases} held-out customer messages that the models never saw in training. Thresholds were
          tuned on a separate dev set. Re-run with <code className="rounded bg-slate-100 px-1">make eval</code>.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Delta label="Intent accuracy" before={intentBase} after={intentNow} hint="Regex rules" />
        <Delta label="Right article in top 3" before={retrievalBase} after={retrievalNow} hint="Keyword search" />
        <Delta label="Escalation F1" before={base.escalation_f1} after={now.escalation_f1} hint="Old pipeline" />
        <Delta label="Self-service rate" before={base.self_service_rate} after={now.self_service_rate} hint="Old pipeline" />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
          <h2 className="text-sm font-semibold text-slate-800">Intent classification</h2>
          <p className="mb-4 text-xs text-slate-500">Accuracy on 13 intents (macro F1 on the right)</p>
          <MethodBars
            production={PRODUCTION_INTENT}
            rows={Object.entries(report.intents).map(([name, m]) => ({
              name,
              value: m.accuracy,
              detail: `${pct(m.accuracy)} · F1 ${pct(m.macro_f1)}`,
            }))}
          />
        </section>
        <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
          <h2 className="text-sm font-semibold text-slate-800">Knowledge-base retrieval</h2>
          <p className="mb-4 text-xs text-slate-500">
            Recall@3 on {report.n_with_article} questions with a known answer (Recall@1 and MRR on the right)
          </p>
          <MethodBars
            production={PRODUCTION_RETRIEVAL}
            rows={Object.entries(report.retrieval).map(([name, m]) => ({
              name,
              value: m.recall_at_3,
              detail: `${pct(m.recall_at_3)} · R@1 ${pct(m.recall_at_1)} · MRR ${m.mrr.toFixed(2)}`,
            }))}
          />
        </section>
      </div>

      <section className="mt-6 overflow-x-auto rounded-2xl bg-white ring-1 ring-slate-200">
        <div className="p-5 pb-3">
          <h2 className="text-sm font-semibold text-slate-800">When to hand off to a human (end to end)</h2>
          <p className="text-xs text-slate-500">Full pipeline, offline provider, one new conversation per message</p>
        </div>
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-y border-slate-200 text-xs text-slate-500">
            <tr>
              <th className="px-5 py-2.5 font-medium">Pipeline</th>
              <th className="px-3 py-2.5 text-right font-medium">Precision</th>
              <th className="px-3 py-2.5 text-right font-medium">Recall</th>
              <th className="px-3 py-2.5 text-right font-medium">F1</th>
              <th className="px-3 py-2.5 text-right font-medium">Self-service</th>
              <th className="px-3 py-2.5 text-right font-medium">Right article</th>
              <th className="px-5 py-2.5 text-right font-medium">Latency</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 tabular-nums">
            {Object.entries(report.escalation).map(([name, m]) => (
              <tr key={name} className={name === CURRENT ? "bg-brand-50/60 font-medium text-slate-900" : "text-slate-600"}>
                <td className="px-5 py-3">{name}</td>
                <td className="px-3 py-3 text-right">{pct(m.escalation_precision)}</td>
                <td className="px-3 py-3 text-right">{pct(m.escalation_recall)}</td>
                <td className="px-3 py-3 text-right">{pct(m.escalation_f1)}</td>
                <td className="px-3 py-3 text-right">{pct(m.self_service_rate)}</td>
                <td className="px-3 py-3 text-right">{pct(m.answered_from_right_article)}</td>
                <td className="px-5 py-3 text-right">{Math.round(m.median_latency_ms)} ms</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="px-5 py-3 text-xs text-slate-500">
          Precision: handed-off chats that really needed a person. Recall: chats that needed a person and got one.
        </p>
      </section>

      <section className="mt-6 rounded-2xl bg-white p-5 ring-1 ring-slate-200">
        <h2 className="text-sm font-semibold text-slate-800">Where the intent model is still wrong</h2>
        <p className="mb-3 text-xs text-slate-500">Shown on purpose: these are the next training examples to add</p>
        <ul className="divide-y divide-slate-100 text-sm">
          {report.intent_errors.map(([text, gold, pred]) => (
            <li key={text} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span className="text-slate-700">“{text}”</span>
              <span className="text-xs text-slate-500">
                expected <b className="text-slate-700">{INTENT_LABELS[gold] ?? gold}</b>, got{" "}
                <b className="text-red-700">{INTENT_LABELS[pred] ?? pred}</b>
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
