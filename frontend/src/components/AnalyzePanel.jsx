import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { CATEGORY_ORDER, cat, pct } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { AnalyzerBadge, CategoryBadge, Chip, SectionTitle } from './ui'

const SAMPLES = [
  {
    label: 'EN · Cyber + infra',
    title: 'Hackers hit water utility in Riga',
    text: 'A hacktivist group claimed it breached the SCADA system of a water treatment plant in Riga, exploiting CVE-2025-1234 in an exposed HMI. The utility confirmed a brief supply disruption.',
  },
  {
    label: 'SQ · Dezinformim',
    title: '',
    text: 'Një video deepfake e kryeministrit që njofton mobilizim po përhapet nga llogari të rreme në TikTok dhe Telegram në Prishtinë. Verifikuesit e fakteve thonë se janë lajme të rreme. #MobilizimiTani',
  },
  {
    label: 'SQ · Infrastrukturë',
    title: '',
    text: 'Sulm kibernetik ndaj operatorit të rrjetit elektrik shkakton ndërprerje të rrymës në Mitrovicë dhe Prizren; hakerët pretendojnë qasje në sistemin SCADA.',
  },
  {
    label: 'DE · Physisch',
    title: '',
    text: 'Drohnen über einem Kraftwerk bei Wien gesichtet; die Polizei ermittelt wegen möglicher Sabotage an einer nahegelegenen Bahnstrecke.',
  },
]

export default function AnalyzePanel() {
  const { t } = useI18n()
  const [samples, setSamples] = useState(SAMPLES)
  const [title, setTitle] = useState(SAMPLES[0].title)
  const [text, setText] = useState(SAMPLES[0].text)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // Samples come from the backend so their AI answers can be cached for the offline demo.
  useEffect(() => {
    api.samples().then((s) => s?.length && setSamples(s)).catch(() => {})
  }, [])

  const run = async () => {
    setBusy(true); setError(null)
    try { setResult(await api.analyze({ title, text })) } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const maxKw = result?.keyword_scores ? Math.max(1, ...Object.values(result.keyword_scores)) : 1

  return (
    <div className="grid gap-4 p-4 lg:grid-cols-2">
      <div className="panel p-4">
        <SectionTitle>{t('a.paste')}</SectionTitle>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {samples.map((s) => (
            <button key={s.label} onClick={() => { setTitle(s.title); setText(s.text); setResult(null) }} title={s.cached ? t('a.cachedSample') : ''} className="rounded-md px-2 py-1 text-[11px] text-slate-400 ring-1 ring-slate-700 hover:text-slate-200">
              {s.label}{s.cached && <span className="ml-1 text-emerald-400">●</span>}
            </button>
          ))}
        </div>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t('a.titlePh')} className="mb-2 w-full rounded-lg bg-slate-950/70 px-3 py-2 text-sm ring-1 ring-slate-700 outline-none focus:ring-cyan-500/60" />
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={9} className="w-full rounded-lg bg-slate-950/70 px-3 py-2 text-sm leading-relaxed ring-1 ring-slate-700 outline-none focus:ring-cyan-500/60" />
        <button onClick={run} disabled={busy || text.trim().length < 3} className="mt-3 rounded-lg bg-cyan-500/20 px-4 py-2 text-sm font-medium text-cyan-200 ring-1 ring-cyan-500/40 hover:bg-cyan-500/30 disabled:opacity-50">
          {busy ? t('a.running') : t('a.run')}
        </button>
        {error && <div className="mt-2 text-sm text-red-400">{error}</div>}
      </div>

      <div className="panel p-4">
        <SectionTitle>{t('a.output')}</SectionTitle>
        {!result && <div className="py-10 text-center text-sm text-slate-500">{t('a.empty')}</div>}
        {result && (
          <div className="space-y-4 text-sm">
            <div className="flex flex-wrap items-center gap-3">
              <CategoryBadge category={result.category} />
              {result.tags.map((tg) => <CategoryBadge key={tg} category={tg} small />)}
              <AnalyzerBadge value={result.analyzer} />
              {result.cached && <span className="rounded px-1.5 py-0.5 text-[10px] text-amber-300 ring-1 ring-amber-500/30">{t('a.cached')}</span>}
              {result.offline && <span className="rounded px-1.5 py-0.5 text-[10px] text-amber-300 ring-1 ring-amber-500/30">{t('a.offlineLocal')}</span>}
            </div>
            <div className="grid grid-cols-3 gap-3">
              {[[t('a.severity'), result.severity.toFixed(2)], [t('a.confidence'), pct(result.confidence)], [t('a.region'), result.location?.zone || '—']].map(([k, v]) => (
                <div key={k} className="rounded-lg bg-slate-950/60 p-3 ring-1 ring-slate-800">
                  <div className="text-[10px] uppercase tracking-widest text-slate-500">{k}</div>
                  <div className="mt-1 font-mono text-lg text-slate-100">{v}</div>
                </div>
              ))}
            </div>
            <p className="text-slate-300">{result.rationale}</p>
            {result.baseline && (
              <div className="rounded-lg bg-slate-950/60 p-3 text-xs ring-1 ring-slate-800">
                <div className="mb-1.5 text-[10px] uppercase tracking-widest text-slate-500">{t('a.baseline')}</div>
                <div className="flex flex-wrap items-center gap-3 text-slate-400">
                  <CategoryBadge category={result.baseline.category} small />
                  <span>{t('a.severity')} <span className="font-mono text-slate-300">{result.baseline.severity.toFixed(2)}</span></span>
                  <span>{t('a.confidence')} <span className="font-mono text-slate-300">{pct(result.baseline.confidence)}</span></span>
                  <span className={result.baseline.category === result.category ? 'text-emerald-400' : 'text-amber-300'}>
                    {result.baseline.category === result.category ? `✓ ${t('a.agree')}` : `≠ ${t('a.disagree')}`}
                  </span>
                </div>
              </div>
            )}
            {result.keyword_scores && (
              <div className="space-y-1.5">
                {CATEGORY_ORDER.map((c) => (
                  <div key={c} className="flex items-center gap-2 text-xs">
                    <span className="w-28 text-slate-400">{t(`cat.${c}`).split(' ')[0]}</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
                      <div className="h-full rounded-full" style={{ width: `${((result.keyword_scores[c] || 0) / maxKw) * 100}%`, background: cat(c).color }} />
                    </div>
                    <span className="w-6 text-right font-mono text-slate-500">{result.keyword_scores[c] || 0}</span>
                  </div>
                ))}
              </div>
            )}
            <div className="space-y-2">
              {Object.entries(result.entities).filter(([, v]) => v?.length).map(([k, vals]) => (
                <div key={k} className="flex flex-wrap items-center gap-1.5">
                  <span className="w-24 text-[10px] uppercase tracking-widest text-slate-500">{k}</span>
                  {vals.map((v) => <Chip key={v}>{v}</Chip>)}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
