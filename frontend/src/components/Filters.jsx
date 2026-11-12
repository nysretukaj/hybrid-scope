import { CATEGORY_ORDER, cat } from '../lib/format'

const SOURCES = [
  ['all', 'All'],
  ['synthetic', 'Scenario'],
  ['live', 'Live'],
]

export default function Filters({ filters, setFilters, zones }) {
  const set = (k, v) => setFilters((f) => ({ ...f, [k]: v }))
  return (
    <div className="panel space-y-3 p-3">
      <input
        value={filters.q}
        onChange={(e) => set('q', e.target.value)}
        placeholder="Search actors, places, narratives…"
        className="w-full rounded-lg bg-slate-950/70 px-3 py-2 text-sm text-slate-200 ring-1 ring-slate-700 outline-none placeholder:text-slate-600 focus:ring-cyan-500/60"
      />

      <div className="flex flex-wrap gap-1.5">
        <button
          onClick={() => set('category', '')}
          className={`rounded-md px-2 py-1 text-[11px] ring-1 ${!filters.category ? 'bg-slate-700 text-white ring-slate-500' : 'text-slate-400 ring-slate-700 hover:text-slate-200'}`}
        >
          All domains
        </button>
        {CATEGORY_ORDER.map((c) => {
          const m = cat(c)
          const active = filters.category === c
          return (
            <button
              key={c}
              onClick={() => set('category', active ? '' : c)}
              className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] ring-1 transition ${active ? `${m.bg} ${m.text} ${m.ring}` : 'text-slate-400 ring-slate-700 hover:text-slate-200'}`}
            >
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: m.color }} />
              {m.label.split(' ')[0]}
            </button>
          )
        })}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <select
          value={filters.zone}
          onChange={(e) => set('zone', e.target.value)}
          className="rounded-lg bg-slate-950/70 px-2 py-1.5 text-xs text-slate-300 ring-1 ring-slate-700 outline-none"
        >
          <option value="">All regions</option>
          {zones.map((z) => <option key={z} value={z}>{z}</option>)}
        </select>
        <div className="flex rounded-lg bg-slate-950/70 p-0.5 ring-1 ring-slate-700">
          {SOURCES.map(([k, label]) => (
            <button
              key={k}
              onClick={() => set('source', k)}
              className={`flex-1 rounded-md px-1 py-1 text-[11px] ${filters.source === k ? 'bg-slate-700 text-white' : 'text-slate-500 hover:text-slate-300'}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <label className="flex flex-1 items-center gap-2 text-[11px] text-slate-400">
          <span className="whitespace-nowrap">Min confidence</span>
          <input
            type="range" min="0" max="0.95" step="0.05"
            value={filters.min_confidence}
            onChange={(e) => set('min_confidence', Number(e.target.value))}
            className="w-full accent-cyan-400"
          />
          <span className="w-8 font-mono text-slate-300">{Math.round(filters.min_confidence * 100)}%</span>
        </label>
        <label className="flex cursor-pointer items-center gap-1.5 text-[11px] text-slate-400">
          <input
            type="checkbox" checked={filters.hybrid_only}
            onChange={(e) => set('hybrid_only', e.target.checked)}
            className="accent-fuchsia-400"
          />
          Hybrid only
        </label>
      </div>
    </div>
  )
}
