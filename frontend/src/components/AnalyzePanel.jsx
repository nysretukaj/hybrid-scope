import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { CATEGORY_ORDER, cat, causeLabel, pct } from '../lib/format'
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

const MAX_IMAGE_BYTES = 5 * 1024 * 1024
const VOTE_ICON = { rules: '📏', model: '🧠', local_llm: '💻', cloud_llm: '☁️' }

/** Which analyzers voted for which category, and how much they agree. */
function Votes({ result }) {
  const { t } = useI18n()
  if (!result.votes?.length) return null
  return (
    <div className="rounded-lg bg-slate-950/60 p-3 ring-1 ring-slate-800">
      <div className="mb-2 flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-500">
        {t('a.votes')}
        <span className="ml-auto normal-case tracking-normal text-slate-400">{t('a.agreement', { n: Math.round((result.agreement || 0) * 100) })}</span>
      </div>
      <div className="space-y-1.5">
        {result.votes.map((v) => (
          <div key={v.source} className="flex items-center gap-2 text-xs">
            <span className="w-40 text-slate-300">{VOTE_ICON[v.source]} {t(`a.vote.${v.source}`)}</span>
            <CategoryBadge category={v.category} small />
            <span className="font-mono text-slate-400">{pct(v.confidence)}</span>
            {v.category === result.category ? <span className="text-emerald-400">✓</span> : <span className="text-amber-300">≠</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function AnalyzePanel({ localAi }) {
  const { t, lang } = useI18n()
  const [samples, setSamples] = useState(SAMPLES)
  const [title, setTitle] = useState(SAMPLES[0].title)
  const [text, setText] = useState(SAMPLES[0].text)
  const [image, setImage] = useState(null) // data URL of a picture to analyse with the text
  const [useLocal, setUseLocal] = useState(true)
  const [result, setResult] = useState(null)
  const [lastRequest, setLastRequest] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const localReady = !!localAi?.available && !!localAi?.chat_model

  const pickImage = (file) => {
    setError(null)
    if (!file) { setImage(null); return }
    if (!file.type.startsWith('image/')) { setError(t('a.notImage')); return }
    if (file.size > MAX_IMAGE_BYTES) { setError(t('a.imageTooBig')); return }
    const reader = new FileReader()
    reader.onload = () => setImage(String(reader.result))
    reader.readAsDataURL(file)
  }

  // Samples come from the backend so their AI answers can be cached for the offline demo.
  useEffect(() => {
    api.samples().then((s) => s?.length && setSamples(s)).catch(() => {})
  }, [])

  const request = async (body) => {
    setBusy(true); setError(null)
    try {
      setResult(await api.analyze(body, lang))
      setLastRequest(body)
    } catch (e) {
      setError(e.status === 429 ? t('a.rateLimited') : e.message)
    } finally {
      setBusy(false)
    }
  }
  const run = () => request({ title, text, use_local: useLocal && localReady, image_base64: image || undefined })

  // Switching language re-renders the last result in that language (served from the cache, no new AI call).
  // A local-AI analysis is not repeated: on this computer it can take a minute.
  useEffect(() => {
    if (lastRequest && !lastRequest.use_local && !lastRequest.image_base64) request(lastRequest)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang])

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

        <div className="mt-3 flex flex-wrap items-center gap-3">
          <label className={`flex cursor-pointer items-center gap-2 rounded-lg px-3 py-1.5 text-xs ring-1 ${localReady ? 'text-slate-300 ring-slate-700 hover:bg-slate-800' : 'cursor-not-allowed text-slate-600 ring-slate-800'}`}
            title={localReady ? '' : t('a.localOff')}>
            🖼️ {image ? t('a.imageChange') : t('a.imageAdd')}
            <input type="file" accept="image/*" className="hidden" disabled={!localReady} onChange={(e) => pickImage(e.target.files?.[0])} />
          </label>
          {image && (
            <span className="flex items-center gap-2">
              <img src={image} alt="" className="h-10 w-10 rounded object-cover ring-1 ring-slate-700" />
              <button onClick={() => setImage(null)} className="text-xs text-slate-400 hover:text-slate-200">✕ {t('a.imageRemove')}</button>
            </span>
          )}
          <label className={`flex items-center gap-2 text-xs ${localReady ? 'text-slate-300' : 'text-slate-600'}`}>
            <input type="checkbox" checked={useLocal && localReady} disabled={!localReady} onChange={(e) => setUseLocal(e.target.checked)} className="accent-emerald-400" />
            💻 {t('a.useLocal')}
          </label>
        </div>
        {!localReady && <p className="mt-2 text-[11px] text-slate-500">{t('a.localOff')}</p>}

        <button onClick={run} disabled={busy || text.trim().length < 3} className="mt-3 rounded-lg bg-cyan-500/20 px-4 py-2 text-sm font-medium text-cyan-200 ring-1 ring-cyan-500/40 hover:bg-cyan-500/30 disabled:opacity-50">
          {busy ? (useLocal && localReady ? t('a.runningLocal') : t('a.running')) : t('a.run')}
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
              {[[t('a.severity'), result.severity.toFixed(2)], [t('a.confidence'), pct(result.confidence)], [t('a.region'), result.location?.zone_label || result.location?.zone || '—']].map(([k, v]) => (
                <div key={k} className="rounded-lg bg-slate-950/60 p-3 ring-1 ring-slate-800">
                  <div className="text-[10px] uppercase tracking-widest text-slate-500">{k}</div>
                  <div className="mt-1 font-mono text-lg text-slate-100">{v}</div>
                </div>
              ))}
            </div>
            {result.category !== 'other' && (result.subcategory || result.cause || result.claim || result.target) && (
              <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                {[
                  [t('a.sub'), result.subcategory && t(`sub.${result.subcategory}`)],
                  [t('a.cause'), result.cause && causeLabel(t, result.cause, [result.category])],
                  [t('a.claim'), result.claim && t(`claim.${result.claim}`)],
                  [t('a.target'), result.target],
                ].map(([k, v]) => (
                  <div key={k} className="rounded-lg bg-slate-950/60 px-3 py-2 ring-1 ring-slate-800">
                    <div className="text-[10px] uppercase tracking-widest text-slate-500">{k}</div>
                    <div className="mt-0.5 text-slate-200">{v || '—'}</div>
                  </div>
                ))}
              </div>
            )}
            <p className="text-slate-300">{result.rationale}</p>
            {(result.image_preview || result.image_findings) && (
              <div className="flex gap-3 rounded-lg bg-slate-950/60 p-3 ring-1 ring-slate-800">
                {result.image_preview && <img src={`data:image/jpeg;base64,${result.image_preview}`} alt="" className="h-20 w-20 shrink-0 rounded object-cover" />}
                <div className="text-xs">
                  <div className="mb-1 text-[10px] uppercase tracking-widest text-slate-500">🖼️ {t('a.imageResult')}</div>
                  <p className="text-slate-300">{result.image_skipped ? t('a.imageSkipped') : (result.image_findings || '—')}</p>
                </div>
              </div>
            )}
            <Votes result={result} />
            {result.examples?.length > 0 && (
              <div className="rounded-lg bg-slate-950/60 p-3 text-xs ring-1 ring-slate-800">
                <div className="mb-1.5 text-[10px] uppercase tracking-widest text-slate-500">📚 {t('a.examples')}</div>
                <ul className="space-y-1">
                  {result.examples.map((ex) => (
                    <li key={ex.title} className="flex items-center gap-2 text-slate-400">
                      <CategoryBadge category={ex.category} small />
                      <span className="truncate" title={ex.title}>{ex.title}</span>
                      <span className="ml-auto font-mono text-slate-500">{Math.round(ex.similarity * 100)}%</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
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
                  <span className="w-24 text-[10px] uppercase tracking-widest text-slate-500">{t(`ent.${k}`)}</span>
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
