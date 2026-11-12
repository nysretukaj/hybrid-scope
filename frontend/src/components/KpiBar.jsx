import { useI18n } from '../lib/i18n'

function Kpi({ label, value, sub, accent }) {
  return (
    <div className="panel flex min-w-0 flex-col px-4 py-3">
      <span className="truncate text-[10px] uppercase tracking-[0.16em] text-slate-500">{label}</span>
      <span className="mt-1 font-mono text-2xl font-semibold" style={{ color: accent || '#e2e8f0' }}>{value ?? '–'}</span>
      {sub && <span className="truncate text-[11px] text-slate-500" title={sub}>{sub}</span>}
    </div>
  )
}

export default function KpiBar({ stats }) {
  const { t } = useI18n()
  const s = stats || {}
  const reduction = s.signals_total && s.alerts ? Math.round((1 - s.alerts / s.signals_total) * 100) : null
  return (
    <div className="no-print grid grid-cols-2 gap-3 px-4 pt-4 sm:grid-cols-3 xl:grid-cols-6">
      <Kpi label={t('kpi.critical')} value={s.critical_alerts} accent="#f87171" sub={t('kpi.criticalSub')} />
      <Kpi label={t('kpi.hybrid')} value={s.hybrid_alerts} accent="#e879f9" sub={t('kpi.hybridSub')} />
      <Kpi label={t('kpi.active')} value={s.alerts} sub={reduction != null ? t('kpi.lessNoise', { n: reduction }) : ''} />
      <Kpi label={t('kpi.signals24')} value={s.signals_24h} sub={t('kpi.inWindow', { n: s.signals_total ?? '–' })} />
      <Kpi label={t('kpi.relevant')} value={s.threat_relevant} accent="#22d3ee" sub={t('kpi.relevantSub')} />
      <Kpi label={t('kpi.sources')} value={s.sources} sub={t('kpi.sourcesSub', { live: s.live_signals ?? 0, scenario: s.synthetic_signals ?? 0 })} />
    </div>
  )
}
