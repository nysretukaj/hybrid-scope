import { useCallback, useState } from 'react'
import { cat, fmtTime, level, pct, timeAgo } from '../lib/format'
import { useI18n } from '../lib/i18n'
import BriefModal, { ttpUrl } from './BriefModal'
import CorrelationTimeline from './CorrelationTimeline'
import ReplayPanel from './ReplayPanel'
import { AnalyzerBadge, CategoryBadge, Chip, Help, LevelBadge, ReliabilityBar, ScoreRing, SectionTitle } from './ui'

/** The alert explained in two or three everyday sentences, for readers who are not analysts. */
function PlainSummary({ alert }) {
  const { t } = useI18n()
  const zone = alert.zone_label || alert.zone
  const names = alert.categories.map((c) => t(`cat.${c}`).split(' ')[0].toLowerCase())
  const what = alert.is_hybrid
    ? t('pl.hybrid', { n: alert.categories.length, zone, cats: names.join(', ') })
    : alert.categories.length > 1
      ? t('pl.multi', { zone })
      : t('pl.single', { cat: names[0] || '', zone })
  const color = level(alert.level).color
  return (
    <div className="mt-4 rounded-xl p-4 ring-1" style={{ background: `${color}12`, '--tw-ring-color': `${color}50` }}>
      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.14em]" style={{ color }}>💬 {t('pl.title')}</div>
      <p className="text-sm leading-relaxed text-slate-200">{what}</p>
      <p className="mt-1.5 text-sm font-semibold leading-relaxed text-slate-100">{t(`pl.level.${alert.level}`)}</p>
      <p className="mt-1.5 flex items-center text-xs text-slate-400">
        {t('pl.basis', { n: alert.signal_count, k: alert.source_count })}<Help term="sources" />
      </p>
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

function FeedbackBar({ alert, onFeedback, onClearFeedback, notifyEnabled, onNotify, publicMode }) {
  const { t } = useI18n()
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const run = async (fn) => { setBusy(true); try { await fn() } finally { setBusy(false) } }
  const fb = alert.feedback

  if (publicMode) {
    return (
      <div className="mt-4 rounded-lg bg-slate-950/50 p-2.5 text-[11px] text-slate-500 ring-1 ring-slate-800">
        {t('d.publicReadOnly')}
      </div>
    )
  }

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg bg-slate-950/50 p-2.5 ring-1 ring-slate-800">
      {fb ? (
        <>
          <span className={`rounded-md px-2 py-1 text-[10px] font-bold tracking-widest ring-1 ${fb.verdict === 'confirmed' ? 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/40' : 'bg-slate-500/15 text-slate-300 ring-slate-500/40'}`}>
            {fb.verdict === 'confirmed' ? `✓ ${t('d.confirmed')}` : `✗ ${t('d.dismissed')}`}
          </span>
          {fb.note && <span className="text-xs italic text-slate-400">“{fb.note}”</span>}
          <span className="text-[11px] text-slate-600">{timeAgo(fb.at)}</span>
          <button disabled={busy} onClick={() => run(onClearFeedback)} className="ml-auto rounded-md px-2 py-1 text-[11px] text-slate-400 ring-1 ring-slate-700 hover:text-slate-200">{t('d.undo')}</button>
        </>
      ) : (
        <>
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder={t('d.note')} className="min-w-40 flex-1 rounded-md bg-slate-900 px-2.5 py-1.5 text-xs text-slate-200 ring-1 ring-slate-700 outline-none focus:ring-cyan-500/50" />
          <button disabled={busy} onClick={() => run(() => onFeedback('confirmed', note))} className="rounded-md bg-emerald-500/15 px-3 py-1.5 text-xs font-medium text-emerald-200 ring-1 ring-emerald-500/40 hover:bg-emerald-500/25">✓ {t('d.confirm')}</button>
          <button disabled={busy} onClick={() => run(() => onFeedback('false_positive', note))} className="rounded-md px-3 py-1.5 text-xs text-slate-300 ring-1 ring-slate-600 hover:bg-slate-800">✗ {t('d.fp')}</button>
        </>
      )}
      {notifyEnabled && (
        <button disabled={busy} onClick={() => run(onNotify)} className="rounded-md bg-sky-500/15 px-3 py-1.5 text-xs text-sky-200 ring-1 ring-sky-500/40 hover:bg-sky-500/25">➤ {t('d.send')}</button>
      )}
      <div className="w-full text-[10px] text-slate-600">{t('d.feedbackHint')}</div>
    </div>
  )
}

function Evidence({ signal, active, links }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const related = links.filter((l) => l.source === signal.id || l.target === signal.id)
  return (
    <div id={`ev-${signal.id}`} className={`rounded-lg p-3 ring-1 transition ${active ? 'bg-slate-800/70 ring-slate-400' : 'bg-slate-900/40 ring-slate-800'}`}>
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        <CategoryBadge category={signal.category} />
        {signal.tags?.map((tg) => <span key={tg} className={`text-[10px] ${cat(tg).text}`}>+{t(`cat.${tg}`).split(' ')[0].toLowerCase()}</span>)}
        <span className="font-mono">{fmtTime(signal.timestamp)}</span>
        <span>({timeAgo(signal.timestamp)})</span>
        <span className="ml-auto font-mono text-slate-400" title={t('ui.priority')}>P{Math.round(signal.score)}</span>
      </div>
      <div className="mt-1.5 text-sm font-medium text-slate-100">{signal.title}</div>
      <p className="mt-1 text-[13px] leading-relaxed text-slate-400">{signal.text}</p>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-slate-500">
        <span className="text-slate-300">{signal.source_label || signal.source_name}</span>
        <span>{signal.source_type_label || signal.source_type}</span>
        <ReliabilityBar value={signal.source_reliability} />
        {signal.source_reliability_prior != null && (
          <span className="text-emerald-400/80">{t('d.relAdjusted', { a: signal.source_reliability_prior, b: signal.source_reliability })}</span>
        )}
        <span>{t('ui.sevConf', { s: signal.severity, c: pct(signal.confidence) })}</span>
        {signal.url
          ? <a href={signal.url} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline">{t('d.open')}</a>
          : <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-300 ring-1 ring-amber-500/30">{t('d.synthetic')}</span>}
      </div>

      <button onClick={() => setOpen((o) => !o)} className="mt-2 text-[11px] text-slate-400 hover:text-slate-200">
        {open ? '▾' : '▸'} {t('d.ai')} ({related.length})
      </button>
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

export default function AlertDetail({ alert, loading, source, notifyEnabled, onFeedback, onClearFeedback, onNotify, publicMode }) {
  const { t, mode } = useI18n()
  const [techOpen, setTechOpen] = useState(null) // null = follow the view mode
  const showTech = techOpen ?? mode === 'expert'
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

      <PlainSummary alert={alert} />

      <FeedbackBar alert={alert} onFeedback={onFeedback} onClearFeedback={onClearFeedback} notifyEnabled={notifyEnabled} onNotify={onNotify} publicMode={publicMode} />

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
            <Evidence key={s.id} signal={s} active={s.id === activeSignal} links={alert.links} />
          ))}
        </div>
      </div>

      {briefOpen && <BriefModal alertId={alert.id} source={source} onClose={() => setBriefOpen(false)} />}
    </div>
  )
}
