import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../lib/api'
import { fmtTime, pct } from '../lib/format'
import { useI18n } from '../lib/i18n'

export const ttpUrl = (tp) =>
  tp.framework.startsWith('ATT&CK') ? `https://attack.mitre.org/techniques/${tp.id.replace('.', '/')}/` : null

const LEVEL_INK = { CRITICAL: '#b91c1c', HIGH: '#c2410c', MEDIUM: '#a16207', LOW: '#475569' }

function H({ children }) {
  return <h3 className="mb-2 mt-7 border-b border-slate-300 pb-1 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500">{children}</h3>
}

export default function BriefModal({ alertId, source, onClose }) {
  const { t } = useI18n()
  const [b, setB] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.brief(alertId, source).then(setB).catch((e) => setError(e.message))
  }, [alertId, source])

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    document.body.classList.add('brief-open')
    return () => { window.removeEventListener('keydown', onKey); document.body.classList.remove('brief-open') }
  }, [onClose])

  return createPortal(
    <div className="brief-overlay fixed inset-0 z-[4000] overflow-y-auto bg-black/75 backdrop-blur-sm" onClick={onClose}>
      <div className="no-print sticky top-0 z-10 flex justify-end gap-2 p-3">
        <button onClick={(e) => { e.stopPropagation(); window.print() }} disabled={!b} className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-50">
          ⤓ {t('b.export')}
        </button>
        <button onClick={onClose} className="rounded-lg bg-slate-800 px-4 py-2 text-sm text-slate-200 ring-1 ring-slate-600 hover:bg-slate-700">{t('b.close')}</button>
      </div>

      <article className="print-area mx-auto mb-10 max-w-3xl rounded-sm bg-white px-10 py-9 text-[13.5px] leading-relaxed text-slate-800 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        {error && <div className="text-red-700">{error}</div>}
        {!b && !error && <div className="py-20 text-center text-slate-400">…</div>}
        {b && (
          <>
            <div className="text-center font-mono text-[11px] font-bold tracking-[0.2em] text-amber-700">{b.classification}</div>
            <div className="mt-5 flex items-start justify-between gap-6 border-b-2 border-slate-900 pb-4">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">HybridScope · {t('b.title')}</div>
                <h1 className="mt-1 text-2xl font-bold leading-tight text-slate-900">{b.title}</h1>
              </div>
              <div className="shrink-0 text-right">
                <div className="font-mono text-4xl font-bold" style={{ color: LEVEL_INK[b.level] }}>{Math.round(b.score)}</div>
                <div className="text-[11px] font-bold tracking-widest" style={{ color: LEVEL_INK[b.level] }}>{b.level}</div>
              </div>
            </div>
            <dl className="mt-3 grid grid-cols-3 gap-4 text-xs">
              <div><dt className="text-slate-500">{t('b.period')}</dt><dd className="font-medium">{fmtTime(b.period.from)} – {fmtTime(b.period.to)}</dd></div>
              <div><dt className="text-slate-500">{t('d.confidence')}</dt><dd className="font-medium">{pct(b.confidence)} · {b.likelihood}</dd></div>
              <div><dt className="text-slate-500">{t('b.risk')}</dt><dd className="font-medium">{b.level} ({Math.round(b.score)}/100)</dd></div>
            </dl>

            <H>{t('b.bluf')}</H>
            <p className="rounded bg-slate-100 p-3 font-medium text-slate-900">{b.bluf}</p>

            <H>{t('b.judgments')}</H>
            <ol className="list-decimal space-y-1.5 pl-5">
              {b.key_judgments.map((j, k) => <li key={k}>{j}</li>)}
            </ol>

            {b.ttps.length > 0 && (
              <>
                <H>{t('b.ttps')}</H>
                <table className="w-full text-left text-xs">
                  <tbody>
                    {b.ttps.map((tp) => (
                      <tr key={tp.id} className="border-b border-slate-200">
                        <td className="py-1 pr-3 text-slate-500">{tp.framework}</td>
                        <td className="py-1 pr-3 font-mono font-semibold">
                          {ttpUrl(tp) ? <a href={ttpUrl(tp)} target="_blank" rel="noreferrer" className="text-cyan-800 underline">{tp.id}</a> : tp.id}
                        </td>
                        <td className="py-1 pr-3">{tp.name}</td>
                        <td className="py-1 pr-3 text-slate-500">{tp.tactic}</td>
                        <td className="py-1 text-right font-mono text-slate-500">×{tp.signal_ids.length}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}

            <H>{t('b.indicators')}</H>
            <ul className="list-disc space-y-1 pl-5">{b.indicators.map((x, k) => <li key={k}>{x}</li>)}</ul>

            <H>{t('b.actions')}</H>
            <ol className="list-decimal space-y-1 pl-5">{b.actions.map((x, k) => <li key={k}>{x}</li>)}</ol>

            <H>{t('b.sources')} ({b.sources.length})</H>
            <table className="w-full text-left text-[11px]">
              <tbody>
                {b.sources.map((s, k) => (
                  <tr key={k} className="border-b border-slate-200 align-top">
                    <td className="whitespace-nowrap py-1 pr-3 font-mono text-slate-500">{fmtTime(s.time)}</td>
                    <td className="py-1 pr-3">{s.url ? <a href={s.url} className="text-cyan-800 underline" target="_blank" rel="noreferrer">{s.title}</a> : s.title}</td>
                    <td className="py-1 pr-3 text-slate-500">{s.source}</td>
                    <td className="py-1 text-right font-mono text-slate-500">{Math.round(s.reliability * 100)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <p className="mt-6 text-[10.5px] italic text-slate-500">{t('b.method')}: {b.method}</p>
            <div className="mt-6 text-center font-mono text-[11px] font-bold tracking-[0.2em] text-amber-700">{b.classification}</div>
          </>
        )}
      </article>
    </div>,
    document.body,
  )
}
