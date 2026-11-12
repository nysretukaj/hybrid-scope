import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { CATEGORY_ORDER, timeAgo } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { AnalyzerBadge, CategoryBadge, ReliabilityBar } from './ui'

export default function SignalStream({ source, alertsCount, refreshKey }) {
  const { t } = useI18n()
  const [category, setCategory] = useState('')
  const [q, setQ] = useState('')
  const [data, setData] = useState({ total: 0, signals: [] })
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    api.signals({ category, q, source, limit: 400 })
      .then((d) => alive && (setData(d), setError(null)))
      .catch((e) => alive && setError(e.message))
    return () => { alive = false }
  }, [category, q, source, refreshKey])

  return (
    <div className="p-4">
      <div className="panel mb-4 flex flex-wrap items-center gap-3 p-3">
        <div className="mr-auto">
          <div className="text-sm text-slate-200">
            {t('s.raw')} <span className="font-mono text-cyan-300">{data.total}</span> {t('s.items')}
          </div>
          <div className="text-xs text-slate-500">
            {t('s.firehose')} <span className="text-slate-300">{alertsCount}</span> {t('s.alerts')}
          </div>
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t('s.search')}
          className="w-56 rounded-lg bg-slate-950/70 px-3 py-1.5 text-sm ring-1 ring-slate-700 outline-none focus:ring-cyan-500/60"
        />
        <select value={category} onChange={(e) => setCategory(e.target.value)} className="rounded-lg bg-slate-950/70 px-2 py-1.5 text-sm ring-1 ring-slate-700 outline-none">
          <option value="">{t('s.allCats')}</option>
          {[...CATEGORY_ORDER, 'other'].map((c) => <option key={c} value={c}>{t(`cat.${c}`)}</option>)}
        </select>
      </div>
      {error && <div className="mb-3 text-sm text-red-400">{error}</div>}

      <div className="panel overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-[10px] uppercase tracking-[0.14em] text-slate-500">
            <tr className="border-b border-slate-800">
              {['time', 'category', 'signal', 'region', 'source', 'severity', 'analyzer'].map((h) => (
                <th key={h} className="px-3 py-2.5 font-medium">{t(`th.${h}`)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.signals.map((s) => (
              <tr key={s.id} className={`border-b border-slate-800/60 align-top hover:bg-slate-800/30 ${s.category === 'other' ? 'opacity-50' : ''}`}>
                <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-slate-500">{timeAgo(s.timestamp)}</td>
                <td className="px-3 py-2"><CategoryBadge category={s.category} small /></td>
                <td className="max-w-xl px-3 py-2">
                  {s.url
                    ? <a href={s.url} target="_blank" rel="noreferrer" className="text-slate-200 hover:text-cyan-300">{s.title}</a>
                    : <span className="text-slate-200">{s.title}</span>}
                  {(s.entities?.cves?.length > 0 || s.entities?.actors?.length > 0) && (
                    <div className="mt-0.5 text-[11px] text-slate-500">{[...(s.entities.actors || []), ...(s.entities.cves || [])].join(' · ')}</div>
                  )}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-400">{s.zone || <span className="text-slate-600">{t('s.unresolved')}</span>}</td>
                <td className="px-3 py-2 text-xs">
                  <div className="text-slate-300">{s.source_name}</div>
                  <ReliabilityBar value={s.source_reliability} />
                </td>
                <td className="px-3 py-2 font-mono text-xs text-slate-300">{s.severity.toFixed(2)}</td>
                <td className="px-3 py-2"><AnalyzerBadge value={s.analyzer} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
