import { analyzer, timeAgo } from '../lib/format'

const TABS = [
  ['alerts', 'Threat Board'],
  ['signals', 'Signal Stream'],
  ['analyze', 'Analyze Text'],
]

function Logo() {
  return (
    <svg width="34" height="34" viewBox="0 0 32 32" aria-hidden>
      <circle cx="16" cy="16" r="14" fill="none" stroke="#22d3ee" strokeWidth="1.6" opacity="0.9" />
      <circle cx="16" cy="16" r="9" fill="none" stroke="#d946ef" strokeWidth="1.6" opacity="0.8" />
      <path d="M16 16 L16 2 A14 14 0 0 1 28.1 9 Z" fill="#22d3ee" opacity="0.18" />
      <circle cx="16" cy="16" r="2.6" fill="#ef4444" />
      <circle cx="22" cy="9" r="1.4" fill="#f59e0b" />
    </svg>
  )
}

export default function Header({ view, setView, health, busy, onIngest, onReset }) {
  const last = health?.last_ingest
  return (
    <header className="sticky top-0 z-[2000] border-b border-slate-800/80 bg-[#060a13]/90 backdrop-blur">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3">
        <div className="flex items-center gap-3">
          <Logo />
          <div>
            <div className="text-[17px] font-semibold tracking-wide text-slate-100">
              Hybrid<span className="text-cyan-300">Scope</span>
            </div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">OSINT · Hybrid threat intelligence</div>
          </div>
        </div>

        <nav className="flex gap-1 rounded-lg bg-slate-900/80 p-1 ring-1 ring-slate-800">
          {TABS.map(([key, label]) => (
            <button
              key={key}
              onClick={() => setView(key)}
              className={`rounded-md px-3 py-1.5 text-sm transition ${view === key ? 'bg-slate-700/70 text-white shadow' : 'text-slate-400 hover:text-slate-200'}`}
            >
              {label}
            </button>
          ))}
        </nav>

        <div className="ml-auto flex flex-wrap items-center gap-3 text-xs">
          <span className="flex items-center gap-2 text-slate-400">
            <span className="relative inline-block h-2 w-2 rounded-full text-emerald-400 live-dot" style={{ background: 'currentColor' }} />
            Analyzer: <span className="text-slate-200">{health ? analyzer(health.analyzer).label : '-'}</span>
          </span>
          <span className="hidden text-slate-500 md:inline">
            Live ingest: {last ? `${timeAgo(last.finished_at)} · ${last.fetched} items` : 'not run yet'}
          </span>
          <button
            onClick={onIngest}
            disabled={!!busy}
            className="rounded-lg bg-cyan-500/15 px-3 py-1.5 font-medium text-cyan-200 ring-1 ring-cyan-500/40 transition hover:bg-cyan-500/25 disabled:opacity-50"
          >
            {busy === 'ingest' ? 'Ingesting…' : 'Ingest live sources'}
          </button>
          <button
            onClick={onReset}
            disabled={!!busy}
            className="rounded-lg px-3 py-1.5 text-slate-400 ring-1 ring-slate-700 transition hover:text-slate-200 disabled:opacity-50"
            title="Re-anchor the synthetic exercise scenario to the current time"
          >
            {busy === 'reset' ? 'Resetting…' : 'Reset scenario'}
          </button>
        </div>
      </div>
    </header>
  )
}
