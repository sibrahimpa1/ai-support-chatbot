import { ArrowRight, LayoutDashboard, Mountain, RotateCcw, ShieldCheck, Truck } from "lucide-react";
import { Link } from "react-router-dom";
import ChatWidget from "../components/ChatWidget";

const PRODUCTS = [
  { name: "Ridgeline 2P Tent", price: "$249", tag: "Bestseller", hue: "from-emerald-200 to-teal-100" },
  { name: "Cascade 45L Backpack", price: "$179", tag: "New", hue: "from-amber-200 to-orange-100" },
  { name: "Summit Rain Jacket", price: "$159", tag: "Waterproof", hue: "from-sky-200 to-indigo-100" },
  { name: "Basecamp Hiking Boots", price: "$189", tag: "Lifetime warranty", hue: "from-stone-300 to-stone-100" },
];

/** A fictional store page that shows how the widget looks embedded on a real site. */
export default function Storefront() {
  return (
    <div className="min-h-full bg-stone-50">
      <div className="bg-brand-950 px-4 py-2 text-center text-xs text-brand-100">
        Demo store for the AI support chatbot.{" "}
        <Link to="/dashboard" className="font-semibold text-white underline underline-offset-2">
          Open the support team dashboard
        </Link>
      </div>
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
        <div className="flex items-center gap-2 text-lg font-bold text-brand-900">
          <Mountain size={22} /> Fernway Outdoor
        </div>
        <div className="hidden gap-7 text-sm text-slate-600 sm:flex">
          <span>Camping</span>
          <span>Hiking</span>
          <span>Paddling</span>
          <span>Apparel</span>
        </div>
        <Link
          to="/dashboard"
          className="flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:border-brand-600 hover:text-brand-800"
        >
          <LayoutDashboard size={15} /> Agent dashboard
        </Link>
      </nav>

      <header className="mx-auto grid max-w-6xl items-center gap-10 px-4 pt-6 pb-14 sm:px-6 md:grid-cols-2">
        <div>
          <p className="mb-3 text-sm font-semibold tracking-wide text-brand-700 uppercase">Fall collection</p>
          <h1 className="text-4xl leading-tight font-bold text-slate-900 sm:text-5xl">
            Gear built for the long way around.
          </h1>
          <p className="mt-4 max-w-md text-lg text-slate-600">
            Tents, packs and apparel with a lifetime warranty. Questions about an order? Our AI
            assistant answers instantly, day or night.
          </p>
          <div className="mt-7 flex gap-3">
            <button className="flex items-center gap-2 rounded-xl bg-brand-800 px-5 py-3 text-sm font-semibold text-white hover:bg-brand-900">
              Shop new arrivals <ArrowRight size={16} />
            </button>
          </div>
        </div>
        <div className="relative h-72 overflow-hidden rounded-3xl bg-gradient-to-br from-brand-800 via-brand-700 to-emerald-500 sm:h-80">
          <svg viewBox="0 0 400 300" className="absolute inset-0 h-full w-full" preserveAspectRatio="xMidYMax slice">
            <circle cx="300" cy="80" r="34" fill="#fef3c7" opacity="0.9" />
            <path d="M0 300 L90 150 L150 220 L230 110 L330 240 L400 180 L400 300 Z" fill="#14532d" opacity="0.7" />
            <path d="M0 300 L70 220 L140 270 L220 190 L300 260 L400 220 L400 300 Z" fill="#0b2e1a" />
          </svg>
        </div>
      </header>

      <section className="mx-auto grid max-w-6xl gap-4 px-4 sm:grid-cols-3 sm:px-6">
        {[
          { icon: Truck, title: "Free shipping over $75", text: "Ships same day before 2 PM MT" },
          { icon: RotateCcw, title: "60-day returns", text: "90 days for Rewards members" },
          { icon: ShieldCheck, title: "Lifetime warranty", text: "On all Fernway-brand gear" },
        ].map(({ icon: Icon, title, text }) => (
          <div key={title} className="flex items-center gap-3 rounded-2xl bg-white p-4 ring-1 ring-slate-200">
            <div className="rounded-xl bg-brand-50 p-2.5 text-brand-700">
              <Icon size={20} />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-800">{title}</p>
              <p className="text-xs text-slate-500">{text}</p>
            </div>
          </div>
        ))}
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <h2 className="mb-6 text-xl font-bold text-slate-900">Trail favorites</h2>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {PRODUCTS.map((p) => (
            <div key={p.name} className="group">
              <div className={`mb-3 aspect-square rounded-2xl bg-gradient-to-br ${p.hue} ring-1 ring-black/5`} />
              <span className="text-[11px] font-semibold tracking-wide text-brand-700 uppercase">{p.tag}</span>
              <p className="text-sm font-medium text-slate-800">{p.name}</p>
              <p className="text-sm text-slate-500">{p.price}</p>
            </div>
          ))}
        </div>
      </section>

      <ChatWidget defaultOpen />
    </div>
  );
}
