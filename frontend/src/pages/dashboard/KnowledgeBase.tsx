import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type KbArticle } from "../../api";

/** Browse the help-center content the bot answers from, and test retrieval. */
export default function KnowledgeBase() {
  const [query, setQuery] = useState("");
  const [articles, setArticles] = useState<KbArticle[]>([]);

  useEffect(() => {
    const timer = setTimeout(() => api.knowledgeBase(query.trim() || undefined).then(setArticles), 200);
    return () => clearTimeout(timer);
  }, [query]);

  const top = articles[0]?.score;

  return (
    <div className="mx-auto max-w-4xl p-4 sm:p-8">
      <h1 className="text-2xl font-bold text-slate-900">Knowledge base</h1>
      <p className="text-sm text-slate-500">
        The help-center sections the assistant retrieves answers from. Type a customer question to see what the
        retriever (BM25) would pass to the model.
      </p>
      <div className="relative mt-5">
        <Search size={16} className="absolute top-1/2 left-3.5 -translate-y-1/2 text-slate-400" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. can I return boots I already wore?"
          className="w-full rounded-xl border border-slate-200 bg-white py-3 pr-4 pl-10 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
        />
      </div>
      <p className="mt-3 text-xs text-slate-500">
        {query ? `${articles.length} matching sections, ranked by relevance` : `${articles.length} sections`}
      </p>
      <ul className="mt-3 space-y-3">
        {articles.map((a) => (
          <li key={a.id} className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold tracking-wide text-brand-700 uppercase">{a.source}</p>
                <p className="text-sm font-semibold text-slate-800">{a.title}</p>
              </div>
              {a.score != null && top && (
                <div className="w-28 shrink-0 text-right">
                  <p className="text-xs text-slate-500 tabular-nums">score {a.score.toFixed(2)}</p>
                  <div className="mt-1 h-1.5 rounded-full bg-slate-100">
                    <div className="ml-auto h-1.5 rounded-full bg-brand-700" style={{ width: `${(a.score / top) * 100}%` }} />
                  </div>
                </div>
              )}
            </div>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">{a.text}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
