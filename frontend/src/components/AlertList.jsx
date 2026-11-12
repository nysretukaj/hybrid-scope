import { cat, level, pct, timeAgo } from '../lib/format'
import { LevelBadge } from './ui'

export default function AlertList({ alerts, selectedId, onSelect, total }) {
  return (
    <div className="panel flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2.5">
        <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Prioritized alerts</span>
        <span className="font-mono text-[11px] text-slate-500">{alerts.length}/{total}</span>
      </div>
      <div className="scroll-thin min-h-0 flex-1 space-y-1.5 overflow-y-auto p-2">
        {alerts.length === 0 && <div className="p-6 text-center text-sm text-slate-500">No alerts match the filters.</div>}
        {alerts.map((a) => {
          const l = level(a.level)
          const selected = a.id === selectedId
          return (
            <button
              key={a.id}
              onClick={() => onSelect(a.id)}
              className={`group relative w-full overflow-hidden rounded-lg py-2.5 pl-4 pr-3 text-left ring-1 transition ${selected ? 'bg-slate-800/80 ring-slate-500' : 'bg-slate-900/40 ring-slate-800 hover:bg-slate-800/50 hover:ring-slate-700'}`}
            >
              <span className="absolute inset-y-0 left-0 w-1" style={{ background: l.color, boxShadow: selected ? `0 0 12px ${l.color}` : 'none' }} />
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <LevelBadge value={a.level} />
                    {a.is_hybrid && <span className="rounded bg-fuchsia-500/15 px-1.5 py-0.5 text-[9px] font-bold tracking-widest text-fuchsia-300 ring-1 ring-fuchsia-500/40">HYBRID</span>}
                    {!a.synthetic && <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[9px] font-bold tracking-widest text-emerald-300 ring-1 ring-emerald-500/30">LIVE</span>}
                  </div>
                  <div className="mt-1.5 truncate text-sm font-medium text-slate-100">{a.zone}</div>
                  <div className="truncate text-xs text-slate-400" title={a.headline}>{a.headline}</div>
                  <div className="mt-2 flex items-center gap-3 text-[11px] text-slate-500">
                    <span className="flex gap-1">
                      {a.categories.map((c) => (
                        <span key={c} className="h-2 w-2 rounded-full" title={cat(c).label} style={{ background: cat(c).color }} />
                      ))}
                    </span>
                    <span>{a.signal_count} sig · {a.source_count} src</span>
                    <span>conf {pct(a.confidence)}</span>
                    <span className="ml-auto">{timeAgo(a.last_seen)}</span>
                  </div>
                </div>
                <div className="font-mono text-2xl font-semibold" style={{ color: l.color }}>{Math.round(a.score)}</div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
