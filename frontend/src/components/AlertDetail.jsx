import { useCallback, useState } from 'react'
import { api } from '../lib/api'
import {
  BAND_COLOR, CATEGORY_ORDER, RISK_BAND_COLOR, SUBCATEGORIES, VERIFICATION, VERIFICATION_ORDER,
  cat, causeLabel, fmtCount, fmtTime, level, levelLabel, pct, timeAgo,
} from '../lib/format'
import { useI18n } from '../lib/i18n'
import BriefModal, { ttpUrl } from './BriefModal'
import CorrelationTimeline from './CorrelationTimeline'
import ReplayPanel from './ReplayPanel'
import { AnalyzerBadge, CategoryBadge, Chip, Help, LevelBadge, ReliabilityBar, ScoreRing, SectionTitle } from './ui'

/** The alert explained in two or three everyday sentences, for readers who are not analysts. */
function PlainSummary({ alert, source, aiEnabled }) {
  const { t, lang } = useI18n()
  const [ai, setAi] = useState({ state: 'idle', text: '' })
  const zone = alert.zone_label || alert.zone
  const names = alert.categories.map((c) => t(`cat.${c}`).split(' ')[0].toLowerCase())
  const what = alert.is_hybrid
    ? t('pl.hybrid', { n: alert.categories.length, zone, cats: names.join(', ') })
    : alert.categories.length > 1
      ? t('pl.multi', { zone })
      : t('pl.single', { cat: names[0] || '', zone })
  const color = level(alert.level).color
  const as = alert.assessment || {}
  const askAi = () => {
    setAi({ state: 'loading', text: '' })
    api.aiSummary(alert.id, source, lang)
      .then((r) => setAi({ state: 'done', text: r.summary }))
      .catch(() => setAi({ state: 'error', text: t('pl.aiError') }))
  }
  return (
    <div className="mt-4 rounded-xl p-4 ring-1" style={{ background: `${color}12`, '--tw-ring-color': `${color}50` }}>
      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.14em]" style={{ color }}>💬 {t('pl.title')}</div>
      <p className="text-sm leading-relaxed text-slate-200">{what}</p>
      <p className="mt-1.5 text-sm font-semibold leading-relaxed text-slate-100">{t(`pl.level.${alert.level}`)}</p>
      {as.cause && <p className="mt-1.5 text-sm text-slate-300">{t('pl.cause', { c: causeLabel(t, as.cause, alert.categories) })}</p>}
      {as.uncertain && ['HIGH', 'CRITICAL'].includes(as.severity_level) && (
        <p className="mt-2 rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-200 ring-1 ring-amber-500/30">⚠ {t('pl.uncertain')}</p>
      )}
      <p className="mt-1.5 flex items-center text-xs text-slate-400">
        {t('pl.basis', { n: alert.signal_count, k: alert.source_count })}<Help term="sources" />
      </p>
      {aiEnabled && (
        <div className="mt-3">
          {ai.state === 'idle' && (
            <button onClick={askAi} className="rounded-lg bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-200 ring-1 ring-emerald-500/30 hover:bg-emerald-500/20">
              ✨ {t('pl.aiBtn')}
            </button>
          )}
          {ai.state === 'loading' && <span className="text-xs text-slate-400">{t('pl.aiLoading')}</span>}
          {(ai.state === 'done' || ai.state === 'error') && (
            <p className={`rounded-lg px-3 py-2 text-sm leading-relaxed ring-1 ${ai.state === 'done' ? 'bg-emerald-500/5 text-slate-200 ring-emerald-500/20' : 'text-slate-400 ring-slate-700'}`}>
              {ai.state === 'done' && <span className="mb-1 block text-[10px] uppercase tracking-widest text-emerald-300">✨ {t('pl.aiLabel')}</span>}
              {ai.text}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

/** Six plain tiles: how bad, how sure, how big, how urgent, how widespread, how solid the evidence. */
function Assessment({ alert }) {
  const { t } = useI18n()
  const as = alert.assessment
  if (!as) return null
  const tiles = [
    { key: 'severity', value: levelLabel(as.severity_level), color: level(as.severity_level).color },
    { key: 'confidence', value: t(`band.${as.confidence_level}`), color: BAND_COLOR[as.confidence_level], help: 'confidence' },
    { key: 'impact', value: t(`band.${as.impact}`), color: RISK_BAND_COLOR[as.impact],
      sub: as.affected ? t('as.affected', { n: fmtCount(as.affected) }) : as.critical_sector ? t('as.criticalSector') : null },
    { key: 'urgency', value: t(`band.${as.urgency}`), color: RISK_BAND_COLOR[as.urgency] },
    { key: 'scope', value: t(`scope.${as.scope}`), color: '#cbd5e1',
      sub: alert.geo_precision === 'country' ? t('as.approx') : null },
    { key: 'evidence', value: t(`band.${as.evidence_quality}`), color: BAND_COLOR[as.evidence_quality], help: 'evidence',
      sub: t('as.indep', { n: as.independent_sources }) + (as.duplicates ? ` · ${t('as.dups', { n: as.duplicates })}` : '') },
  ]
  return (
    <div className="mt-4">
      <SectionTitle>{t('as.title')}</SectionTitle>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {tiles.map((x) => (
          <div key={x.key} className="rounded-lg bg-slate-900/50 px-3 py-2 ring-1 ring-slate-800">
            <div className="flex items-center text-[10px] uppercase tracking-[0.12em] text-slate-500">
              {t(`as.${x.key}`)}{x.help && <Help term={x.help} />}
            </div>
            <div className="mt-0.5 text-sm font-semibold" style={{ color: x.color }}>{x.value}</div>
            {x.sub && <div className="text-[11px] text-slate-500">{x.sub}</div>}
          </div>
        ))}
      </div>
    </div>
  )
}

const BAR_COLORS = { severity: '#f87171', hybrid: '#e879f9', corroboration: '#22d3ee', recency: '#f59e0b', reliability: '#34d399' }
const ENTITY_ICON = { actor: '◆', organisation: '▣', technology: '⚙', CVE: '⚠', narrative: '#' }
const FW_STYLE = {
  DISARM: 'bg-fuchsia-500/10 text-fuchsia-200 ring-fuchsia-500/30',
  'ATT&CK': 'bg-cyan-500/10 text-cyan-200 ring-cyan-500/30',
  'ATT&CK for ICS': 'bg-amber-500/10 text-amber-200 ring-amber-500/30',
}

function ScoreBreakdown({ breakdown, score }) {
  const { t } = useI18n()
  return (
    <div>
      <SectionTitle right={<span className="font-mono text-xs text-slate-400">Σ {score}</span>}><span className="flex items-center">{t('d.why')}<Help term="score" align="right" /></span></SectionTitle>
      <div className="space-y-2.5">
        {breakdown.map((b) => (
          <div key={b.key}>
            <div className="flex items-baseline justify-between text-xs">
              <span className="text-slate-300">{t(`sc.${b.key}`)}</span>
              <span className="font-mono text-slate-400"><span className="text-slate-100">{b.points}</span> / {b.max_points}</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-800">
              <div className="h-full rounded-full transition-all duration-500" style={{ width: `${(b.points / b.max_points) * 100}%`, background: BAR_COLORS[b.key] }} />
            </div>
            <div className="mt-0.5 text-[11px] text-slate-500">{b.explanation}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Sequence({ sequence, firstSeen }) {
  const { t } = useI18n()
  const start = new Date(firstSeen).getTime()
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {sequence.map((s, i) => (
        <span key={s.category} className="flex items-center gap-1.5">
          {i > 0 && <span className="text-slate-600">→</span>}
          <span className={`rounded-md px-2 py-1 text-[11px] ring-1 ${cat(s.category).bg} ${cat(s.category).text} ${cat(s.category).ring}`}>
            {t(`cat.${s.category}`).split(' ')[0]}
            <span className="ml-1.5 font-mono text-[10px] opacity-70">+{Math.round((new Date(s.first_seen).getTime() - start) / 36e5)}h</span>
          </span>
        </span>
      ))}
    </div>
  )
}

function Ttps({ ttps, onJump }) {
  const { t } = useI18n()
  if (!ttps?.length) return null
  return (
    <div className="mt-6">
      <SectionTitle right={<span className="text-[11px] text-slate-500">{t('d.ttpHint')}</span>}>{t('d.ttps')}</SectionTitle>
      <div className="flex flex-wrap gap-1.5">
        {ttps.map((tp) => (
          <button
            key={tp.id}
            onClick={() => onJump(tp.signal_ids[tp.signal_ids.length - 1])}
            title={`${tp.framework} · ${tp.tactic}${ttpUrl(tp) ? `\n${ttpUrl(tp)}` : ''}`}
            className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] ring-1 transition hover:brightness-125 ${FW_STYLE[tp.framework]}`}
          >
            <span className="font-mono font-semibold">{tp.id}</span>
            <span className="opacity-80">{tp.name}</span>
            <span className="rounded bg-black/30 px-1 font-mono text-[9px]">×{tp.signal_ids.length}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

/** Verification status in five simple steps, from "not checked yet" to "confirmed" or "disproved". */
function VerificationBar({ alert, onFeedback, notifyEnabled, onNotify, publicMode }) {
  const { t } = useI18n()
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const run = async (fn) => { setBusy(true); try { await fn() } finally { setBusy(false) } }
  const current = alert.verification || 'unverified'
  const fb = alert.feedback

  return (
    <div className="mt-4 rounded-lg bg-slate-950/50 p-3 ring-1 ring-slate-800">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="flex items-center text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
          {t('v.title')}<Help term="verification" />
        </span>
        {fb?.note && <span className="text-xs italic text-slate-400">“{fb.note}”</span>}
        {fb?.at && <span className="text-[11px] text-slate-600">{timeAgo(fb.at)}</span>}
      </div>
      <div className="flex flex-wrap gap-1.5" role="group" aria-label={t('v.title')}>
        {VERIFICATION_ORDER.map((v) => {
          const active = v === current
          const style = VERIFICATION[v]
          return (
            <button key={v} disabled={busy || publicMode || active} onClick={() => run(() => onFeedback(v, note))}
              aria-pressed={active}
              className={`rounded-full px-3 py-1 text-xs ring-1 transition ${active ? 'font-semibold text-slate-950' : 'text-slate-300 ring-slate-700 hover:bg-slate-800 disabled:hover:bg-transparent'} ${publicMode && !active ? 'opacity-40' : ''}`}
              style={active ? { background: style.color, '--tw-ring-color': style.color } : undefined}>
              {style.icon} {t(`v.${v}`)}
            </button>
          )
        })}
      </div>
      {publicMode ? (
        <div className="mt-2 text-[11px] text-slate-500">{t('d.publicReadOnly')}</div>
      ) : (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder={t('d.note')}
            className="min-w-40 flex-1 rounded-md bg-slate-900 px-2.5 py-1.5 text-xs text-slate-200 ring-1 ring-slate-700 outline-none focus:ring-cyan-500/50" />
          {notifyEnabled && (
            <button disabled={busy} onClick={() => run(onNotify)} className="rounded-md bg-sky-500/15 px-3 py-1.5 text-xs text-sky-200 ring-1 ring-sky-500/40 hover:bg-sky-500/25">➤ {t('d.send')}</button>
          )}
          <div className="w-full text-[10px] text-slate-600">{t('v.hint')}</div>
        </div>
      )}
    </div>
  )
}

/** Small editor for an analyst to correct a report's category and subcategory. */
function Reclassify({ signal, onSave, onCancel }) {
  const { t } = useI18n()
  const [category, setCategory] = useState(signal.category)
  const [sub, setSub] = useState(signal.subcategory || '')
  const [busy, setBusy] = useState(false)
  const save = async () => { setBusy(true); try { await onSave(signal.id, category, sub || null) } finally { setBusy(false) } }
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg bg-slate-950/60 p-2 ring-1 ring-amber-500/30">
      <select value={category} onChange={(e) => { setCategory(e.target.value); setSub('') }}
        className="rounded-md bg-slate-900 px-2 py-1 text-xs text-slate-200 ring-1 ring-slate-700">
        {[...CATEGORY_ORDER, 'other'].map((c) => <option key={c} value={c}>{t(`cat.${c}`)}</option>)}
      </select>
      {SUBCATEGORIES[category] && (
        <select value={sub} onChange={(e) => setSub(e.target.value)}
          className="rounded-md bg-slate-900 px-2 py-1 text-xs text-slate-200 ring-1 ring-slate-700">
          <option value="">{t('sub.general')}</option>
          {SUBCATEGORIES[category].map((s) => <option key={s} value={s}>{t(`sub.${s}`)}</option>)}
        </select>
      )}
      <button disabled={busy} onClick={save} className="rounded-md bg-amber-500/20 px-3 py-1 text-xs font-medium text-amber-100 ring-1 ring-amber-500/40 hover:bg-amber-500/30">{t('ev.save')}</button>
      <button onClick={onCancel} className="rounded-md px-2 py-1 text-xs text-slate-400 hover:text-slate-200">{t('ev.cancel')}</button>
    </div>
  )
}

/** One-line facts about a report, in plain words: what kind, why, how it is stated, who is targeted. */
function EvidenceFacts({ signal }) {
  const { t } = useI18n()
  const chip = 'rounded px-1.5 py-0.5 text-[10px] ring-1'
  return (
    <div className="mt-1.5 flex flex-wrap gap-1.5">
      {signal.subcategory && signal.subcategory !== 'general' && (
        <span className={`${chip} ${cat(signal.category).text} ring-slate-700`}>{t(`sub.${signal.subcategory}`)}</span>
      )}
      {signal.cause && signal.cause !== 'unknown' && (
        <span className={`${chip} text-slate-300 ring-slate-700`}>{causeLabel(t, signal.cause, [signal.category])}</span>
      )}
      {signal.claim && signal.claim !== 'reported' && (
        <span className={`${chip} ${signal.claim === 'confirmed' ? 'text-emerald-300 ring-emerald-500/30' : 'text-amber-300 ring-amber-500/30'}`}>
          {t(`claim.${signal.claim}`)}
        </span>
      )}
      {signal.target && <span className={`${chip} text-slate-300 ring-slate-700`}>🎯 {signal.target}</span>}
      {signal.geo_precision === 'country' && <span className={`${chip} text-slate-400 ring-slate-700`}>⌖ {t('ev.approx')}</span>}
      {signal.stale && <span className={`${chip} text-orange-300 ring-orange-500/30`}>⏳ {t('ev.stale')}</span>}
      {signal.duplicate_of && <span className={`${chip} text-slate-400 ring-slate-600`}>⧉ {t('ev.dup')}</span>}
      {signal.uncertain && <span className={`${chip} text-amber-300 ring-amber-500/30`}>? {t('ev.uncertain')}</span>}
    </div>
  )
}

/** The article's picture, described by the local vision model. The server fetches the image and sends
 *  back a small preview, so the browser never loads third-party pictures. */
function EvidenceImage({ signal, localAi }) {
  const { t } = useI18n()
  const [state, setState] = useState({ status: 'idle' })
  if (!signal.image_url) return null
  const run = () => {
    setState({ status: 'loading' })
    api.signalImage(signal.id)
      .then((r) => setState({ status: 'done', r }))
      .catch((e) => setState({ status: 'error', msg: e.message }))
  }
  if (state.status === 'idle') {
    return localAi ? (
      <button onClick={run} className="mt-2 text-[11px] text-teal-300 hover:text-teal-200">🖼️ {t('ev.imageAnalyze')}</button>
    ) : null
  }
  if (state.status === 'loading') return <div className="mt-2 text-[11px] text-slate-400">🖼️ {t('ev.imageLoading')}</div>
  if (state.status === 'error') return <div className="mt-2 text-[11px] text-amber-300/80">🖼️ {state.msg}</div>
  const r = state.r
  return (
    <div className="mt-2 flex gap-3 rounded-lg bg-slate-950/60 p-2.5 ring-1 ring-slate-800">
      {r.preview && <img src={`data:image/jpeg;base64,${r.preview}`} alt="" className="h-20 w-24 shrink-0 rounded object-cover" />}
      <div className="min-w-0 text-xs">
        <p className="text-slate-200">{r.description}</p>
        {r.visible_text && <p className="mt-1 text-slate-400">“{r.visible_text}”</p>}
        <div className="mt-1 flex flex-wrap gap-2 text-[10px]">
          <span className={r.threat_relevant ? 'text-amber-300' : 'text-slate-500'}>{r.threat_relevant ? t('ev.imageRelevant') : t('ev.imageNotRelevant')}</span>
          {r.signs_of_manipulation?.length > 0 && <span className="text-orange-300">⚠ {t('ev.imageSigns')}: {r.signs_of_manipulation.join('; ')}</span>}
        </div>
        <p className="mt-1 text-[10px] text-slate-600">{t('ev.imageNote')}</p>
      </div>
    </div>
  )
}

const VERDICT_COLOR = { coordinated: '#f87171', possibly_coordinated: '#f59e0b', not_coordinated: '#34d399', insufficient_evidence: '#94a3b8' }

/** Second opinion from the local LLM: is this one coordinated hybrid campaign? */
function LocalVerification({ alert, source }) {
  const { t, lang } = useI18n()
  const [state, setState] = useState({ status: 'idle' })
  const run = () => {
    setState({ status: 'loading' })
    api.verifyAi(alert.id, source, lang)
      .then((r) => setState({ status: 'done', r }))
      .catch((e) => setState({ status: 'error', msg: e.message }))
  }
  if (state.status === 'idle') {
    return (
      <button onClick={run} className="mt-3 w-full rounded-lg bg-teal-500/10 px-3 py-2 text-left text-sm text-teal-100 ring-1 ring-teal-500/30 hover:bg-teal-500/20">
        💻 {t('lv2.btn')}
        <span className="block text-[11px] text-slate-400">{t('lv2.sub')}</span>
      </button>
    )
  }
  if (state.status === 'loading') return <div className="mt-3 rounded-lg px-3 py-2 text-sm text-slate-400 ring-1 ring-slate-800">⏳ {t('lv2.loading')}</div>
  if (state.status === 'error') return <div className="mt-3 rounded-lg px-3 py-2 text-sm text-amber-300 ring-1 ring-amber-500/30">⚠ {state.msg}</div>
  const r = state.r
  const color = VERDICT_COLOR[r.verdict]
  return (
    <div className="mt-3 rounded-lg p-3 ring-1" style={{ background: `${color}12`, '--tw-ring-color': `${color}55` }}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] uppercase tracking-widest text-slate-400">💻 {t('lv2.title')}</span>
        <span className="rounded-full px-2 py-0.5 text-xs font-semibold text-slate-950" style={{ background: color }}>{t(`lv2.v.${r.verdict}`)}</span>
        <span className="text-xs text-slate-400">{t('d.confidence')} {pct(r.confidence)}</span>
      </div>
      {r.summary && <p className="mt-2 text-sm text-slate-200">{r.summary}</p>}
      {r.reasons?.length > 0 && (
        <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-slate-300">{r.reasons.map((x) => <li key={x}>{x}</li>)}</ul>
      )}
      {r.missing_evidence?.length > 0 && (
        <div className="mt-2 text-xs text-slate-400">
          <span className="font-medium">{t('lv2.missing')}:</span> {r.missing_evidence.join('; ')}
        </div>
      )}
      <p className="mt-2 text-[10px] text-slate-600">{t('lv2.note', { m: r.model, s: r.seconds })}</p>
    </div>
  )
}

function Evidence({ signal, active, links, canEdit, onReclassify, localAi }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const related = links.filter((l) => l.source === signal.id || l.target === signal.id)
  return (
    <div id={`ev-${signal.id}`} className={`rounded-lg p-3 ring-1 transition ${active ? 'bg-slate-800/70 ring-slate-400' : 'bg-slate-900/40 ring-slate-800'} ${signal.duplicate_of ? 'opacity-70' : ''}`}>
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        <CategoryBadge category={signal.category} />
        {signal.tags?.map((tg) => <span key={tg} className={`text-[10px] ${cat(tg).text}`}>+{t(`cat.${tg}`).split(' ')[0].toLowerCase()}</span>)}
        <span className="font-mono">{fmtTime(signal.timestamp)}</span>
        <span>({timeAgo(signal.timestamp)})</span>
        <span className="ml-auto font-mono text-slate-400" title={t('ui.priority')}>P{Math.round(signal.score)}</span>
      </div>
      <div className="mt-1.5 text-sm font-medium text-slate-100">{signal.title}</div>
      <p className="mt-1 text-[13px] leading-relaxed text-slate-400">{signal.text}</p>
      <EvidenceFacts signal={signal} />
      <EvidenceImage signal={signal} localAi={localAi} />
      {signal.analyzer === 'analyst' && signal.original_category && (
        <div className="mt-1 text-[11px] text-amber-300/80">✎ {t('ev.fixed', { c: t(`cat.${signal.original_category}`) })}</div>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-slate-500">
        <span className="text-slate-300">{signal.source_label || signal.source_name}</span>
        <span>{signal.source_type_label || signal.source_type}</span>
        <ReliabilityBar value={signal.source_reliability} />
        {signal.source_reliability_prior != null && (
          <span className="text-emerald-400/80">{t('d.relAdjusted', { a: signal.source_reliability_prior, b: signal.source_reliability })}</span>
        )}
        <span>{t('ui.sevConf', { s: signal.severity, c: pct(signal.confidence) })}</span>
        {signal.url
          ? <>
            <a href={signal.url} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline">{t('d.open')}</a>
            <a href={`https://web.archive.org/web/*/${signal.url}`} target="_blank" rel="noreferrer" title={t('ev.archiveTip')}
              className="text-slate-400 hover:text-slate-200 hover:underline">{t('ev.archive')}</a>
          </>
          : <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-300 ring-1 ring-amber-500/30">{t('d.synthetic')}</span>}
        {signal.ingested_at && <span title={signal.content_hash ? `SHA-256 ${signal.content_hash}` : undefined}>{t('ev.collected', { t: fmtTime(signal.ingested_at) })}</span>}
      </div>

      <div className="mt-2 flex flex-wrap gap-3">
        <button onClick={() => setOpen((o) => !o)} className="text-[11px] text-slate-400 hover:text-slate-200">
          {open ? '▾' : '▸'} {t('d.ai')} ({related.length})
        </button>
        {canEdit && !editing && (
          <button onClick={() => setEditing(true)} className="text-[11px] text-amber-300/80 hover:text-amber-200">✎ {t('ev.fix')}</button>
        )}
      </div>
      {editing && (
        <Reclassify signal={signal} onCancel={() => setEditing(false)}
          onSave={async (id, c, s) => { await onReclassify(id, c, s); setEditing(false) }} />
      )}
      {open && (
        <div className="mt-2 space-y-2 border-t border-slate-800 pt-2 text-xs">
          <div className="flex items-start gap-2">
            <AnalyzerBadge value={signal.analyzer} />
            <span className="text-slate-300">{signal.rationale}</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(signal.entities || {}).flatMap(([k, vals]) =>
              (vals || []).map((v) => <Chip key={k + v} title={k}>{k === 'locations' ? '⌖ ' : ''}{v}</Chip>),
            )}
          </div>
          {related.length > 0 && (
            <ul className="space-y-0.5 text-slate-500">
              {related.map((l) => <li key={l.source + l.target}>↔ {l.reasons.join(' · ')}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

export default function AlertDetail({ alert, loading, source, notifyEnabled, onFeedback, onNotify, onReclassify, publicMode, aiEnabled, localAi }) {
  const { t } = useI18n()
  const [showTech, setTechOpen] = useState(false)
  const [activeSignal, setActiveSignal] = useState(null)
  const [replayOpen, setReplayOpen] = useState(false)
  const [replayFrame, setReplayFrame] = useState(null)
  const [briefOpen, setBriefOpen] = useState(false)
  const onFrame = useCallback((f) => setReplayFrame(f), [])

  if (!alert) {
    return <div className="panel p-10 text-center text-slate-500">{loading ? t('d.loading') : t('d.select')}</div>
  }

  const selectSignal = (id) => {
    setActiveSignal(id)
    document.getElementById(`ev-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  return (
    <div className="panel p-4 sm:p-5">
      <div className="flex flex-wrap items-start gap-4 sm:gap-5">
        <ScoreRing score={alert.score} levelName={alert.level} size={76} />
        <div className="w-full min-w-0 sm:w-auto sm:flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <LevelBadge value={alert.level} />
            {alert.is_hybrid && <span className="flex items-center rounded-md bg-fuchsia-500/15 px-2 py-0.5 text-[10px] font-bold tracking-widest text-fuchsia-300 ring-1 ring-fuchsia-500/40">{t('d.hybrid')}<Help term="hybrid" /></span>}
            {alert.synthetic && <span className="rounded-md bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300 ring-1 ring-amber-500/30">{t('d.exercise')}</span>}
            <span className="flex items-center text-xs text-slate-500">{t('d.confidence')}&nbsp;<span className="font-mono text-slate-200">{pct(alert.confidence)}</span><Help term="confidence" /></span>
          </div>
          <h2 className="mt-2 text-lg font-semibold text-slate-50 sm:text-xl">{alert.title}</h2>
          {showTech && <p className="mt-1 text-sm text-slate-400">{alert.summary}</p>}
          <div className="mt-3"><Sequence sequence={alert.sequence} firstSeen={alert.first_seen} /></div>
        </div>
        <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto sm:shrink-0 sm:flex-col">
          <button
            onClick={() => setReplayOpen((o) => !o)}
            className={`rounded-lg px-4 py-2 text-left text-sm font-medium ring-1 transition ${replayOpen ? 'bg-fuchsia-500/25 text-fuchsia-100 ring-fuchsia-400/60' : 'bg-fuchsia-500/10 text-fuchsia-200 ring-fuchsia-500/40 hover:bg-fuchsia-500/20'}`}
          >
            ▶ {t('d.replay')}
            <span className="block text-[10px] font-normal opacity-70">{t('d.replaySub')}</span>
          </button>
          <button onClick={() => setBriefOpen(true)} className="rounded-lg bg-slate-100 px-4 py-2 text-left text-sm font-semibold text-slate-900 hover:bg-white">
            ▤ {t('d.brief')}
            <span className="block text-[10px] font-normal opacity-70">{t('d.briefSub')}</span>
          </button>
        </div>
      </div>

      <PlainSummary alert={alert} source={source} aiEnabled={aiEnabled} />
      {localAi && <LocalVerification alert={alert} source={source} />}

      <Assessment alert={alert} />

      <VerificationBar alert={alert} onFeedback={onFeedback} notifyEnabled={notifyEnabled} onNotify={onNotify} publicMode={publicMode} />

      {replayOpen && <ReplayPanel alertId={alert.id} source={source} onFrame={onFrame} onClose={() => setReplayOpen(false)} />}

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <SectionTitle right={<span className="text-[11px] text-slate-500">{t('d.links', { n: alert.links.length })}</span>}>{t('d.timeline')}</SectionTitle>
          <CorrelationTimeline alert={alert} activeId={replayFrame?.signal_id || activeSignal} onSelectSignal={selectSignal} cutoff={replayOpen ? replayFrame?.t : null} />
        </div>
        {showTech && <div className="lg:col-span-2">
          <ScoreBreakdown breakdown={alert.breakdown} score={alert.score} />
        </div>}
      </div>

      <button onClick={() => setTechOpen(!showTech)} aria-expanded={showTech}
        className="mt-6 w-full rounded-lg py-2 text-xs font-medium text-slate-400 ring-1 ring-slate-700 hover:bg-slate-800/50 hover:text-slate-200">
        {showTech ? `▾ ${t('d.techHide')}` : `▸ ${t('d.techShow')}`}
      </button>

      {showTech && <Ttps ttps={alert.ttps} onJump={selectSignal} />}

      {showTech && alert.shared_entities.length > 0 && (
        <div className="mt-6">
          <SectionTitle>{t('d.linking')}</SectionTitle>
          <div className="flex flex-wrap gap-2">
            {alert.shared_entities.slice(0, 14).map((e) => (
              <span key={e.type + e.name} title={t(`et.${e.type}`)} className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800/70 px-2.5 py-1 text-xs text-slate-200 ring-1 ring-slate-700">
                <span className="text-slate-500">{ENTITY_ICON[e.type] || '•'}</span>
                {e.name}
                <span className="rounded bg-slate-950 px-1 font-mono text-[10px] text-slate-400">×{e.count}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-6">
        <SectionTitle right={<span className="text-[11px] text-slate-500">{t('d.sigSrc', { s: alert.signal_count, src: alert.source_count })}</span>}>{t('d.evidence')}</SectionTitle>
        <div className="space-y-2">
          {[...alert.signals].reverse().map((s) => (
            <Evidence key={s.id} signal={s} active={s.id === activeSignal} links={alert.links}
              canEdit={!publicMode} onReclassify={onReclassify} localAi={localAi} />
          ))}
        </div>
      </div>

      {briefOpen && <BriefModal alertId={alert.id} source={source} onClose={() => setBriefOpen(false)} />}
    </div>
  )
}
