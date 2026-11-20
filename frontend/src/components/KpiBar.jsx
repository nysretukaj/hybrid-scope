import { useI18n } from '../lib/i18n'
import { Help } from './ui'

function Kpi({ label, value, sub, accent, help }) {
  return (
    <div className="panel flex min-w-0 flex-col px-3 py-2.5 sm:px-4 sm:py-3">
      <span className="flex items-start text-[10px] uppercase leading-tight tracking-[0.08em] text-slate-500 sm:items-center sm:tracking-[0.16em]">
        <span className="line-clamp-2 sm:truncate">{label}</span>{help && <Help term={help} />}
      </span>
      <span className="mt-1 font-mono text-xl font-semibold sm:text-2xl" style={{ color: accent || '#e2e8f0' }}>{value ?? '–'}</span>
      {sub && <span className="hidden truncate text-[11px] text-slate-500 sm:block" title={sub}>{sub}</span>}
    </div>
  )
}

export default function KpiBar({ stats }) {
  const { t } = useI18n()
  const s = stats || {}
  const reduction = s.signals_total && s.alerts ? Math.round((1 - s.alerts / s.signals_total) * 100) : null
  return (
    <div className="no-print grid grid-cols-3 gap-2 px-3 pt-3 sm:gap-3 sm:px-4 sm:pt-4">
      <Kpi label={t('kpi.critical')} value={s.critical_alerts} accent="#f87171" sub={t('kpi.criticalSub')} help="score" />
      <Kpi label={t('kpi.hybrid')} value={s.hybrid_alerts} accent="#e879f9" sub={t('kpi.hybridSub')} help="hybrid" />
      <Kpi label={t('kpi.active')} value={s.alerts} sub={reduction != null ? t('kpi.lessNoise', { n: reduction }) : ''} />
    </div>
  )
}
