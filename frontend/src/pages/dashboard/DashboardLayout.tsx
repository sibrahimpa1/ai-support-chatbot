import { BookOpen, FlaskConical, Inbox, LayoutDashboard, MessagesSquare, Mountain, Store } from "lucide-react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { api } from "../../api";
import { usePolling } from "../../hooks";

const NAV = [
  { to: "/dashboard", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/dashboard/inbox", label: "Escalations", icon: Inbox },
  { to: "/dashboard/conversations", label: "Conversations", icon: MessagesSquare },
  { to: "/dashboard/knowledge-base", label: "Knowledge base", icon: BookOpen },
  { to: "/dashboard/model-quality", label: "Model quality", icon: FlaskConical },
];

export default function DashboardLayout() {
  const { data: health } = usePolling(api.health, 30000);
  const { data: tickets } = usePolling(api.tickets, 5000);
  const open = tickets?.filter((t) => t.status === "open").length ?? 0;
  const live = health?.provider === "anthropic";

  return (
    <div className="flex min-h-full flex-col bg-slate-50 md:flex-row">
      <aside className="flex shrink-0 flex-col border-slate-200 bg-brand-950 text-brand-100 md:sticky md:top-0 md:h-screen md:w-60 md:border-r">
        <div className="flex items-center gap-2 px-5 py-5 text-white">
          <Mountain size={20} />
          <div>
            <p className="text-sm leading-tight font-bold">Fernway Support</p>
            <p className="text-[11px] text-brand-200">Agent workspace</p>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm whitespace-nowrap transition ${
                  isActive ? "bg-white/10 font-semibold text-white" : "hover:bg-white/5 hover:text-white"
                }`
              }
            >
              <Icon size={17} />
              <span className="flex-1">{label}</span>
              {label === "Escalations" && open > 0 && (
                <span className="rounded-full bg-amber-400 px-1.5 text-[11px] font-bold text-amber-950">{open}</span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto hidden space-y-3 p-4 md:block">
          {health && (
            <div className="rounded-lg bg-white/5 p-3 text-xs">
              <div className="flex items-center gap-2 font-semibold text-white">
                <span className={`h-2 w-2 rounded-full ${live ? "bg-emerald-400" : "bg-amber-400"}`} />
                {live ? "Claude connected" : "Offline demo mode"}
              </div>
              <p className="mt-1 text-brand-200">
                {live ? health.model : "Extractive answers, no API key"} · {health.knowledge_base_chunks} KB sections
                <br />
                NLU: {health.nlu} · search: {health.retrieval}
              </p>
            </div>
          )}
          <Link to="/" className="flex items-center gap-2 text-xs text-brand-200 hover:text-white">
            <Store size={14} /> View demo store & widget
          </Link>
        </div>
      </aside>
      <main className="min-w-0 flex-1">
        <Outlet />
      </main>
    </div>
  );
}
