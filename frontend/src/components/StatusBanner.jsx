import { useEffect, useState } from 'react'
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

function readSeen() {
  try { return localStorage.getItem('hs-onboarded') === '1' } catch { return false }
}

/** First-visit guide: what the page is, then three short steps. The header's 💡 button reopens it. */
export function Onboarding() {
  const { t } = useI18n()
  const [seen, setSeen] = useState(readSeen)
  useEffect(() => {
    const reopen = () => setSeen(false)
    window.addEventListener('hs-guide', reopen)
    return () => window.removeEventListener('hs-guide', reopen)
  }, [])
  if (seen) return null
  const close = () => {
    setSeen(true)
    try { localStorage.setItem('hs-onboarded', '1') } catch { /* storage unavailable */ }
  }
  return (
    <div className="rounded-xl bg-cyan-500/10 p-4 ring-1 ring-cyan-500/30">
      <div className="mb-2 flex items-center gap-2">
        <span aria-hidden>💡</span>
        <span className="text-sm font-semibold text-cyan-100">{t('ob.title')}</span>
        <button onClick={close} className="ml-auto rounded-md bg-cyan-500/20 px-3 py-1 text-xs font-semibold text-cyan-100 hover:bg-cyan-500/30">
          {t('ob.close')}
        </button>
      </div>
      <p className="mb-3 text-sm leading-relaxed text-slate-200">{t('ob.what')}</p>
      <ol className="grid gap-2 text-xs leading-relaxed text-slate-300 sm:grid-cols-3 sm:text-sm">
        {[1, 2, 3].map((i) => (
          <li key={i} className="flex gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/30 text-[11px] font-bold text-cyan-100">{i}</span>
            <span>{t(`ob.${i}`)}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}
