import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { CATEGORY_ORDER, cat, fmtTime, pct } from '../lib/format'
import { useI18n } from '../lib/i18n'

function Card({ icon, title, children }) {
  return (
    <section className="panel min-w-0 p-4">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-100"><span aria-hidden>{icon}</span>{title}</h3>
      {children}
    </section>
  )
}

// "train:category" -> "Training the model (category)" in the page language
function stageLabel(t, stage) {
  const [name, head] = String(stage || 'starting').split(':')
  return t(`ml.stage.${name}`, { h: head ? t(`ml.head.${head}`) : '' })
}

function Dot({ ok }) {
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${ok ? 'bg-emerald-400' : 'bg-slate-600'}`} />
}

function Btn({ children, onClick, disabled, primary }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className={`rounded-lg px-3 py-2 text-sm font-medium ring-1 disabled:cursor-not-allowed disabled:opacity-40 ${primary ? 'bg-emerald-500/20 text-emerald-100 ring-emerald-500/40 hover:bg-emerald-500/30' : 'text-slate-200 ring-slate-700 hover:bg-slate-800'}`}>
      {children}
    </button>
  )
}

/** Accuracy and macro-F1 of the trained model next to the keyword rules, on reports it never saw. */
function Metrics({ info }) {
  const { t } = useI18n()
  const m = info.metrics?.category
  if (!m) return null
  const rows = [
    [t('ml.model'), m.accuracy, m.macro_f1, '#34d399'],
    m.rules_baseline && [t('ml.rules'), m.rules_baseline.accuracy, m.rules_baseline.macro_f1, '#64748b'],
  ].filter(Boolean)
  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-400">{t('ml.metricsHint', { n: m.support })}</p>
      {rows.map(([label, acc, f1, color]) => (
        <div key={label} className="grid grid-cols-[7rem_1fr_3.5rem] items-center gap-2 text-sm">
          <span className="text-slate-300">{label}</span>
          <span className="h-2.5 overflow-hidden rounded-full bg-slate-800"><span className="block h-full rounded-full" style={{ width: `${acc * 100}%`, background: color }} /></span>
          <span className="text-right font-mono text-slate-200">{pct(acc)}</span>
        </div>
      ))}
      <div className="text-xs text-slate-500">
        {t('ml.f1')}: <span className="font-mono text-slate-300">{m.macro_f1.toFixed(2)}</span>
        {m.rules_baseline && <> · {t('ml.rules')}: <span className="font-mono text-slate-300">{m.rules_baseline.macro_f1.toFixed(2)}</span></>}
      </div>
      <details className="text-xs">
        <summary className="cursor-pointer text-slate-400 hover:text-slate-200">{t('ml.perClass')}</summary>
        <table className="mt-2 w-full text-left">
          <thead className="text-[10px] uppercase tracking-wider text-slate-500">
            <tr><th className="py-1">{t('th.category')}</th><th>{t('ml.precision')}</th><th>{t('ml.recall')}</th><th>F1</th><th>n</th></tr>
          </thead>
          <tbody>
            {Object.entries(m.per_class).map(([c, v]) => (
              <tr key={c} className="border-t border-slate-800">
                <td className="py-1" style={{ color: cat(c).color }}>{t(`cat.${c}`)}</td>
                <td className="font-mono">{v.precision.toFixed(2)}</td><td className="font-mono">{v.recall.toFixed(2)}</td>
                <td className="font-mono">{v['f1-score'].toFixed(2)}</td><td className="font-mono text-slate-500">{v.support}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}

export default function ModelPanel({ publicMode, notify }) {
  const { t } = useI18n()
  const [s, setS] = useState(null)
  const [error, setError] = useState(null)
  const [exported, setExported] = useState(null)
  const [busy, setBusy] = useState(null)

  const load = useCallback(() => api.mlStatus().then((d) => { setS(d); setError(null) }).catch((e) => setError(e.message)), [])
  const running = !!s?.job?.running
  useEffect(() => {
    load()
    const id = setInterval(load, running ? 3000 : 15000)
    return () => clearInterval(id)
  }, [load, running])

  const act = async (name, fn, okMsg) => {
    setBusy(name)
    try {
      const r = await fn()
      if (okMsg) notify(okMsg(r))
      await load()
      return r
    } catch (e) {
      notify(e.message, 'err')
      return null
    } finally {
      setBusy(null)
    }
  }

  if (error) return <div className="p-4 text-sm text-red-400">{error}</div>
  if (!s) return <div className="p-10 text-center text-slate-500">{t('d.loading')}</div>

  const o = s.ollama
  const ds = s.dataset
  const info = s.classifier
  const job = s.job
  const canWrite = !publicMode
  const maxCat = Math.max(1, ...Object.values(ds.by_category || {}))

  return (
    <div className="space-y-4 p-3 sm:p-4">
      <p className="max-w-3xl text-sm leading-relaxed text-slate-400">{t('ml.intro')}</p>

      {job.running && (
        <div className="rounded-xl bg-emerald-500/10 p-3 text-sm text-emerald-100 ring-1 ring-emerald-500/30">
          ⏳ {t(`ml.job.${job.job}`)} · {stageLabel(t, job.stage)}
          {job.total > 0 && <> · {job.done}/{job.total}</>}
          {job.total > 0 && (
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800">
              <div className="h-full rounded-full bg-emerald-400 transition-all" style={{ width: `${(job.done / job.total) * 100}%` }} />
            </div>
          )}
        </div>
      )}
      {!job.running && job.error && (
        <div className="rounded-xl bg-red-500/10 p-3 text-sm text-red-200 ring-1 ring-red-500/30">⚠ {job.error}</div>
      )}
      {!job.running && job.result?.labelled != null && (
        <div className="rounded-xl bg-slate-900/60 p-3 text-sm text-slate-300 ring-1 ring-slate-800">
          ✓ {t('ml.labelDone', { n: job.result.labelled, f: job.result.failed, s: job.result.seconds })}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card icon="💻" title={t('ml.engine')}>
          <ul className="space-y-2 text-sm">
            <li className="flex items-center gap-2"><Dot ok={o.available} /> Ollama {o.version ? `v${o.version}` : ''}
              <span className="ml-auto text-xs text-slate-500">{o.available ? t('ml.connected') : t('ml.notRunning')}</span></li>
            <li className="flex items-center gap-2"><Dot ok={o.base_model_ready} /> {o.base_model}
              <span className="ml-auto text-xs text-slate-500">{t('ml.chatRole')}</span></li>
            <li className="flex items-center gap-2"><Dot ok={o.embed_model_ready} /> {o.embed_model}
              <span className="ml-auto text-xs text-slate-500">{t('ml.embedRole')}</span></li>
            <li className="flex items-center gap-2"><Dot ok={o.custom_model_ready} /> {o.custom_model}
              <span className="ml-auto text-xs text-slate-500">{o.custom_model_ready ? t('ml.inUse') : t('ml.notCreated')}</span></li>
          </ul>
          {(!o.available || !o.base_model_ready || !o.embed_model_ready) && (
            <div className="mt-3 rounded-lg bg-slate-950/70 p-3 text-xs text-slate-400 ring-1 ring-slate-800">
              {t('ml.setup')}
              <pre className="mt-2 whitespace-pre-wrap font-mono text-[11px] text-slate-300">ollama pull {o.base_model}{'\n'}ollama pull {o.embed_model}</pre>
            </div>
          )}
          {o.last_error && o.available && <p className="mt-2 text-[11px] text-amber-300/80">⚠ {o.last_error}</p>}
          {canWrite && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Btn onClick={() => act('create', api.mlCreateModel, (r) => t('ml.created', { m: r.model, n: r.examples }))}
                disabled={!o.base_model_ready || !!busy}>
                {busy === 'create' ? t('ml.working') : `🛠️ ${t('ml.createModel')}`}
              </Btn>
              <span className="text-[11px] text-slate-500">{t('ml.createHint')}</span>
            </div>
          )}
        </Card>

        <Card icon="📚" title={t('ml.dataset')}>
          <div className="mb-3 grid grid-cols-3 gap-2 text-center">
            {[[t('ml.labelled'), ds.total], [t('ml.gold'), ds.by_quality?.gold || 0], [t('ml.unlabelled'), ds.unlabelled]].map(([k, v]) => (
              <div key={k} className="rounded-lg bg-slate-950/60 px-2 py-2 ring-1 ring-slate-800">
                <div className="font-mono text-lg text-slate-100">{v}</div>
                <div className="text-[10px] uppercase tracking-wider text-slate-500">{k}</div>
              </div>
            ))}
          </div>
          <div className="space-y-1.5">
            {[...CATEGORY_ORDER, 'other'].map((c) => (
              <div key={c} className="grid grid-cols-[8rem_1fr_2.5rem] items-center gap-2 text-xs">
                <span className="truncate text-slate-400">{t(`cat.${c}`)}</span>
                <span className="h-2 overflow-hidden rounded-full bg-slate-800"><span className="block h-full rounded-full" style={{ width: `${((ds.by_category?.[c] || 0) / maxCat) * 100}%`, background: cat(c).color }} /></span>
                <span className="text-right font-mono text-slate-300">{ds.by_category?.[c] || 0}</span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-slate-500">{t('ml.datasetHint')}</p>
          {canWrite && (
            <div className="mt-3 flex flex-wrap gap-2">
              <Btn onClick={() => act('label', () => api.mlLabel(20), (r) => (r.started ? t('ml.labelStarted', { n: r.queued }) : t('ml.nothingToLabel')))}
                disabled={!o.base_model_ready || running || !!busy}>
                🏷️ {t('ml.label20')}
              </Btn>
              <Btn onClick={async () => setExported(await act('export', api.mlExport))} disabled={!!busy}>
                {busy === 'export' ? t('ml.working') : `📦 ${t('ml.export')}`}
              </Btn>
            </div>
          )}
          {exported && (
            <div className="mt-3 rounded-lg bg-slate-950/70 p-3 text-xs text-slate-300 ring-1 ring-slate-800">
              {t('ml.exported', { n: exported.records, v: exported.verification })}
              <div className="mt-2 flex flex-wrap gap-2">
                {Object.keys(exported.files).map((name) => (
                  <a key={name} href={`/api/ml/export/${name}`} className="rounded bg-slate-800 px-2 py-1 font-mono text-[11px] text-cyan-300 hover:bg-slate-700">⬇ {name}</a>
                ))}
              </div>
            </div>
          )}
        </Card>

        <Card icon="🧠" title={t('ml.training')}>
          {info ? (
            <>
              <div className="mb-3 text-xs text-slate-400">
                {t('ml.trainedAt', { t: fmtTime(info.trained_at) })} · {t(`ml.feat.${info.features}`)} · {t('ml.trainedOn', { n: info.records })}
              </div>
              <Metrics info={info} />
            </>
          ) : <p className="text-sm text-slate-400">{t('ml.notTrained')}</p>}
          {canWrite && (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Btn primary onClick={() => act('train', api.mlTrain, () => t('ml.trainStarted'))} disabled={running || !!busy || ds.total < 30}>
                🚀 {info ? t('ml.retrain') : t('ml.train')}
              </Btn>
              {ds.total < 30 && <span className="text-[11px] text-amber-300/80">{t('ml.needData')}</span>}
            </div>
          )}
          <p className="mt-3 text-[11px] leading-relaxed text-slate-500">{t('ml.trainHint', { p: Math.round(s.classifier_min_prob * 100) })}</p>
        </Card>

        <Card icon="☁️" title={t('ml.finetune')}>
          <p className="text-sm leading-relaxed text-slate-400">{t('ml.finetuneText')}</p>
          <ol className="mt-3 list-decimal space-y-1 pl-5 text-xs text-slate-400">
            <li>{t('ml.ft1')}</li><li>{t('ml.ft2')}</li><li>{t('ml.ft3')}</li><li>{t('ml.ft4')}</li>
          </ol>
          <p className="mt-3 font-mono text-[11px] text-slate-500">training/README.md · training/finetune_lora.py</p>
        </Card>
      </div>
    </div>
  )
}
