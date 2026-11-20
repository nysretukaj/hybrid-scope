import { level, levelLabel } from '../lib/format'
import { useI18n } from '../lib/i18n'

/** One plain-language sentence at the top: is anything urgent, and where? */
export function StatusBanner({ alerts, onOpen }) {
  const { t } = useI18n()
  const critical = alerts.filter((a) => a.level === 'CRITICAL')
  const high = alerts.filter((a) => a.level === 'HIGH')
  const top = critical[0] || high[0]
  const tone = critical.length ? 'CRITICAL' : high.length ? 'HIGH' : 'LOW'
  const text = critical.length ? t('st.critical', { n: critical.length })
    : high.length ? t('st.high', { n: high.length }) : t('st.calm')
  const color = critical.length ? level('CRITICAL').color : high.length ? level('HIGH').color : '#34d399'

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl px-4 py-3 ring-1"
      style={{ background: `${color}14`, boxShadow: `inset 4px 0 0 ${color}`, '--tw-ring-color': `${color}55` }}>
      <span className="text-xl" aria-hidden>{critical.length ? '🚨' : high.length ? '⚠️' : '✅'}</span>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold text-slate-100 sm:text-base">{text}</div>
        {top && (
          <div className="truncate text-xs text-slate-400 sm:text-sm">
            {t('st.top', { zone: top.zone_label || top.zone })} · {levelLabel(top.level)} · {t(`lv.${tone}`)}
          </div>
        )}
      </div>
      {top && (
        <button onClick={() => onOpen(top.id)} className="rounded-lg px-3 py-1.5 text-sm font-semibold text-slate-950"
          style={{ background: color }}>
          {t('st.open')} →
        </button>
      )}
    </div>
  )
}
