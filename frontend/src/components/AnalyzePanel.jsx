import { useState } from 'react'
import { api } from '../lib/api'
import { CATEGORY_ORDER, cat, pct } from '../lib/format'
import { AnalyzerBadge, CategoryBadge, Chip, SectionTitle } from './ui'

const SAMPLES = [
  {
    label: 'Cyber + infrastructure',
    title: 'Hackers hit water utility in Riga',
    text: 'A hacktivist group claimed it breached the SCADA system of a water treatment plant in Riga, exploiting CVE-2025-1234 in an exposed HMI. The utility confirmed a brief supply disruption.',
  },
  {
    label: 'Disinformation',
    title: '',
    text: 'A deepfake video of the prime minister announcing mobilisation is being amplified by a bot network on TikTok and Telegram in Skopje. Fact-checkers have debunked it. #MobilisationNow',
  },
  {
    label: 'Physical',
    title: '',
    text: 'Drones were spotted over a military airbase near Warsaw for the second night; police are investigating possible sabotage of a nearby railway line.',
  },
]

export default function AnalyzePanel() {
  const [title, setTitle] = useState(SAMPLES[0].title)
  const [text, setText] = useState(SAMPLES[0].text)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const run = async () => {
    setBusy(true); setError(null)
    try { setResult(await api.analyze({ title, text })) } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const maxKw = result?.keyword_scores ? Math.max(1, ...Object.values(result.keyword_scores)) : 1

  return (
    <div className="grid gap-4 p-4 lg:grid-cols-2">
      <div className="panel p-4">
        <SectionTitle>Paste any open-source text</SectionTitle>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {SAMPLES.map((s) => (
            <button key={s.label} onClick={() => { setTitle(s.title); setText(s.text); setResult(null) }} className="rounded-md px-2 py-1 text-[11px] text-slate-400 ring-1 ring-slate-700 hover:text-slate-200">
              {s.label}
            </button>
          ))}
        </div>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title (optional)" className="mb-2 w-full rounded-lg bg-slate-950/70 px-3 py-2 text-sm ring-1 ring-slate-700 outline-none focus:ring-cyan-500/60" />
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={9} className="w-full rounded-lg bg-slate-950/70 px-3 py-2 text-sm leading-relaxed ring-1 ring-slate-700 outline-none focus:ring-cyan-500/60" />
        <button onClick={run} disabled={busy || text.trim().length < 3} className="mt-3 rounded-lg bg-cyan-500/20 px-4 py-2 text-sm font-medium text-cyan-200 ring-1 ring-cyan-500/40 hover:bg-cyan-500/30 disabled:opacity-50">
          {busy ? 'Analyzing…' : 'Extract & classify'}
        </button>
        {error && <div className="mt-2 text-sm text-red-400">{error}</div>}
      </div>

      <div className="panel p-4">
        <SectionTitle>AI analysis output</SectionTitle>
        {!result && <div className="py-10 text-center text-sm text-slate-500">Run the analyzer to see entities, classification and severity.</div>}
        {result && (
          <div className="space-y-4 text-sm">
            <div className="flex flex-wrap items-center gap-3">
              <CategoryBadge category={result.category} />
              {result.tags.map((t) => <CategoryBadge key={t} category={t} small />)}
              <AnalyzerBadge value={result.analyzer} />
            </div>
            <div className="grid grid-cols-3 gap-3">
              {[['Severity', result.severity.toFixed(2)], ['Confidence', pct(result.confidence)], ['Region', result.location?.zone || '—']].map(([k, v]) => (
                <div key={k} className="rounded-lg bg-slate-950/60 p-3 ring-1 ring-slate-800">
                  <div className="text-[10px] uppercase tracking-widest text-slate-500">{k}</div>
                  <div className="mt-1 font-mono text-lg text-slate-100">{v}</div>
                </div>
              ))}
            </div>
            <p className="text-slate-300">{result.rationale}</p>
            {result.keyword_scores && (
              <div className="space-y-1.5">
                {CATEGORY_ORDER.map((c) => (
                  <div key={c} className="flex items-center gap-2 text-xs">
                    <span className="w-28 text-slate-400">{cat(c).label.split(' ')[0]}</span>
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
