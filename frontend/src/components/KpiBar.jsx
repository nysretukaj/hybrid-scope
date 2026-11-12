function Kpi({ label, value, sub, accent }) {
  return (
    <div className="panel flex min-w-0 flex-col px-4 py-3">
      <span className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{label}</span>
      <span className="mt-1 font-mono text-2xl font-semibold" style={{ color: accent || '#e2e8f0' }}>{value ?? '–'}</span>
      {sub && <span className="truncate text-[11px] text-slate-500">{sub}</span>}
    </div>
  )
}

export default function KpiBar({ stats }) {
  const s = stats || {}
  const reduction = s.signals_total && s.alerts ? Math.round((1 - s.alerts / s.signals_total) * 100) : null
  return (
    <div className="grid grid-cols-2 gap-3 px-4 pt-4 sm:grid-cols-3 xl:grid-cols-6">
      <Kpi label="Critical alerts" value={s.critical_alerts} accent="#f87171" sub="score ≥ 75" />
      <Kpi label="Hybrid patterns" value={s.hybrid_alerts} accent="#e879f9" sub="cross-domain clusters" />
      <Kpi label="Active alerts" value={s.alerts} sub={reduction != null ? `${reduction}% less noise than raw feed` : ''} />
      <Kpi label="Signals (24h)" value={s.signals_24h} sub={`${s.signals_total ?? '–'} in window`} />
      <Kpi label="Threat-relevant" value={s.threat_relevant} accent="#22d3ee" sub="classified by AI layer" />
      <Kpi label="Sources" value={s.sources} sub={`${s.live_signals ?? 0} live · ${s.synthetic_signals ?? 0} scenario`} />
    </div>
  )
}
