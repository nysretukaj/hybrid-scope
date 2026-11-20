import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { CATEGORY_ORDER, VERIFICATION, VERIFICATION_ORDER, cat, fmtTime, level, levelLabel, timeAgo } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { CategoryBadge, ReliabilityBar } from './ui'

function Card({ title, children, className = '' }) {
  return (
    <section className={`panel min-w-0 p-4 ${className}`}>
      <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{title}</h3>
      {children}
    </section>
  )
}

/** Horizontal bars: label, bar, number. Easy to read at a glance. */
function Bars({ rows, empty }) {
  const max = Math.max(1, ...rows.map((r) => r.value))
  if (!rows.some((r) => r.value)) return <div className="text-sm text-slate-500">{empty}</div>
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.key} className="grid grid-cols-[minmax(0,9rem)_1fr_2.5rem] items-center gap-2 text-sm">
          <span className="truncate text-slate-300" title={r.label}>{r.label}</span>
          <span className="h-2.5 overflow-hidden rounded-full bg-slate-800">
            <span className="block h-full rounded-full" style={{ width: `${(r.value / max) * 100}%`, background: r.color }} />
          </span>
          <span className="text-right font-mono text-slate-200">{r.value}</span>
        </div>
      ))}
    </div>
  )
}

function Number({ label, value, color }) {
  return (
    <div className="panel px-3 py-2.5">
      <div className="text-[10px] uppercase leading-tight tracking-[0.1em] text-slate-500">{label}</div>
      <div className="mt-1 font-mono text-xl font-semibold" style={{ color: color || '#e2e8f0' }}>{value ?? '–'}</div>
    </div>
  )
}

export default function StatsPanel({ source, hours, setHours, refreshKey }) {
  const { t, lang } = useI18n()
  const [s, setS] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    api.stats(source, hours, lang)
      .then((d) => alive && (setS(d), setError(null)))
      .catch((e) => alive && setError(e.message))
    return () => { alive = false }
  }, [source, hours, lang, refreshKey])

  if (error) return <div className="p-4 text-sm text-red-400">{error}</div>
  if (!s) return <div className="p-10 text-center text-slate-500">{t('d.loading')}</div>

  const maxDay = Math.max(1, ...s.trend.map((d) => d.total))
  return (
    <div className="space-y-4 p-3 sm:p-4">
      <div className="flex flex-wrap items-center gap-3">
        <p className="mr-auto text-sm text-slate-400">{t('st2.intro', { d: Math.max(1, Math.round(s.window_hours / 24)) })}</p>
        {setHours && (
          <div className="flex rounded-lg bg-slate-950/70 p-0.5 ring-1 ring-slate-700" role="group" aria-label={t('f.time')}>
            {[24, 72, 168, 0].map((h) => (
              <button key={h} onClick={() => setHours(h)} aria-pressed={hours === h}
                className={`rounded-md px-2.5 py-1 text-xs ${hours === h ? 'bg-slate-700 text-white' : 'text-slate-500 hover:text-slate-300'}`}>
                {t(`time.${h}`)}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <Number label={t('st2.reports')} value={s.signals_total} />
        <Number label={t('st2.relevant')} value={s.threat_relevant} color="#22d3ee" />
        <Number label={t('st2.alerts')} value={s.alerts} />
        <Number label={t('st2.critical')} value={s.critical_alerts} color={level('CRITICAL').color} />
        <Number label={t('st2.infra')} value={s.infrastructure_alerts} color={cat('infrastructure').color} />
        <Number label={t('st2.dups')} value={s.duplicates} color="#94a3b8" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t('st2.byCategory')}>
          <Bars empty={t('st2.none')} rows={CATEGORY_ORDER.map((c) => ({
            key: c, label: t(`cat.${c}`), value: s.by_category[c] || 0, color: cat(c).color,
          }))} />
        </Card>

        <Card title={t('st2.byLevel')}>
          <Bars empty={t('st2.none')} rows={['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((l) => ({
            key: l, label: `${levelLabel(l)} · ${t(`lv.${l}`)}`, value: s.by_level[l] || 0, color: level(l).color,
          }))} />
        </Card>

        <Card title={t('st2.trend')}>
          <div className="flex h-36 items-end gap-1.5">
            {s.trend.map((d) => (
              <div key={d.day} className="flex h-full flex-1 flex-col items-center justify-end gap-1" title={`${fmtTime(d.day)}: ${d.total}`}>
                <span className="font-mono text-[10px] text-slate-400">{d.total || ''}</span>
                <div className="flex w-full flex-col-reverse overflow-hidden rounded-t" style={{ height: `${(d.total / maxDay) * 100}%` }}>
                  {CATEGORY_ORDER.map((c) => d.by_category[c] ? (
                    <span key={c} style={{ height: `${(d.by_category[c] / d.total) * 100}%`, background: cat(c).color }} />
                  ) : null)}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-1 flex justify-between text-[10px] text-slate-500">
            <span>{t('st2.older')}</span><span>{t('st2.today')}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-400">
            {CATEGORY_ORDER.map((c) => (
              <span key={c} className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: cat(c).color }} />{t(`cat.${c}`)}</span>
            ))}
          </div>
        </Card>

        <Card title={t('st2.byCountry')}>
          <Bars empty={t('st2.none')} rows={s.by_country.map((c) => ({ key: c.name, label: c.name, value: c.count, color: '#38bdf8' }))} />
          {s.unlocated > 0 && <p className="mt-2 text-[11px] text-slate-500">{t('st2.unlocated', { n: s.unlocated })}</p>}
        </Card>

        <Card title={t('st2.byVerification')}>
          <Bars empty={t('st2.none')} rows={VERIFICATION_ORDER.map((v) => ({
            key: v, label: `${VERIFICATION[v].icon} ${t(`v.${v}`)}`, value: s.by_verification[v] || 0, color: VERIFICATION[v].color,
          }))} />
        </Card>

        <Card title={t('st2.recent')}>
          {s.recent.length === 0 && <div className="text-sm text-slate-500">{t('st2.none')}</div>}
          <ul className="space-y-2">
            {s.recent.map((r) => (
              <li key={r.id} className="flex items-start gap-2 text-sm">
                <CategoryBadge category={r.category} small />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-slate-200" title={r.title}>{r.title}</div>
                  <div className="text-[11px] text-slate-500">
                    {r.zone_label || t('s.unresolved')} · {timeAgo(r.timestamp)}
                    {r.subcategory && r.subcategory !== 'general' ? ` · ${t(`sub.${r.subcategory}`)}` : ''}
                  </div>
                </div>
                <span className="font-mono text-[10px]" style={{ color: level(r.severity_level).color }}>{levelLabel(r.severity_level)}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title={t('st2.sources')}>
        <p className="mb-3 text-[11px] text-slate-500">{t('st2.sourcesHint')}</p>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
              <tr className="border-b border-slate-800">
                <th className="py-2 pr-3 font-medium">{t('th.source')}</th>
                <th className="py-2 pr-3 font-medium">{t('st2.trust')}</th>
                <th className="py-2 pr-3 text-right font-medium">{t('st2.reports')}</th>
                <th className="py-2 pr-3 text-right font-medium">{t('st2.relevant')}</th>
                <th className="py-2 text-right font-medium">{t('st2.reviews')}</th>
              </tr>
            </thead>
            <tbody>
              {s.source_stats.map((r) => (
                <tr key={r.key} className="border-b border-slate-800/60">
                  <td className="py-1.5 pr-3">
                    <div className="text-slate-200">{r.name}</div>
                    <div className="text-[10px] text-slate-500">{r.type}</div>
                  </td>
                  <td className="py-1.5 pr-3"><ReliabilityBar value={r.reliability} /></td>
                  <td className="py-1.5 pr-3 text-right font-mono text-slate-300">{r.signals}</td>
                  <td className="py-1.5 pr-3 text-right font-mono text-slate-300">{r.relevant}</td>
                  <td className="py-1.5 text-right font-mono text-[11px]">
                    <span className="text-emerald-400">✓{r.confirmed}</span> <span className="text-slate-500">✗{r.rejected}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
