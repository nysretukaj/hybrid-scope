import { useState } from 'react'
import { cat, fmtTime, pct, timeAgo } from '../lib/format'
import CorrelationTimeline from './CorrelationTimeline'
import { AnalyzerBadge, CategoryBadge, Chip, LevelBadge, ReliabilityBar, ScoreRing, SectionTitle } from './ui'

const BAR_COLORS = { severity: '#f87171', hybrid: '#e879f9', corroboration: '#22d3ee', recency: '#f59e0b', reliability: '#34d399' }
const ENTITY_ICON = { actor: '◆', organisation: '▣', technology: '⚙', CVE: '⚠', narrative: '#' }

function ScoreBreakdown({ breakdown, score }) {
  return (
    <div>
      <SectionTitle right={<span className="font-mono text-xs text-slate-400">Σ {score}</span>}>Why this score?</SectionTitle>
      <div className="space-y-2.5">
        {breakdown.map((b) => (
          <div key={b.key}>
            <div className="flex items-baseline justify-between text-xs">
              <span className="text-slate-300">{b.label}</span>
              <span className="font-mono text-slate-400"><span className="text-slate-100">{b.points}</span> / {b.max_points}</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-800">
              <div className="h-full rounded-full" style={{ width: `${(b.points / b.max_points) * 100}%`, background: BAR_COLORS[b.key] }} />
            </div>
            <div className="mt-0.5 text-[11px] text-slate-500">{b.explanation}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Sequence({ sequence, firstSeen }) {
  const start = new Date(firstSeen).getTime()
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {sequence.map((s, i) => (
        <span key={s.category} className="flex items-center gap-1.5">
          {i > 0 && <span className="text-slate-600">→</span>}
          <span className={`rounded-md px-2 py-1 text-[11px] ring-1 ${cat(s.category).bg} ${cat(s.category).text} ${cat(s.category).ring}`}>
            {s.label.split(' ')[0]}
            <span className="ml-1.5 font-mono text-[10px] opacity-70">+{Math.round((new Date(s.first_seen).getTime() - start) / 36e5)}h</span>
          </span>
        </span>
      ))}
    </div>
  )
}

function Evidence({ signal, active, links }) {
  const [open, setOpen] = useState(false)
  const related = links.filter((l) => l.source === signal.id || l.target === signal.id)
  return (
    <div id={`ev-${signal.id}`} className={`rounded-lg p-3 ring-1 transition ${active ? 'bg-slate-800/70 ring-slate-400' : 'bg-slate-900/40 ring-slate-800'}`}>
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        <CategoryBadge category={signal.category} />
        {signal.tags?.map((t) => <span key={t} className={`text-[10px] ${cat(t).text}`}>+{cat(t).label.split(' ')[0].toLowerCase()}</span>)}
        <span className="font-mono">{fmtTime(signal.timestamp)}</span>
        <span>({timeAgo(signal.timestamp)})</span>
        <span className="ml-auto font-mono text-slate-400" title="Per-signal priority = severity × reliability × recency">P{Math.round(signal.score)}</span>
      </div>
      <div className="mt-1.5 text-sm font-medium text-slate-100">{signal.title}</div>
      <p className="mt-1 text-[13px] leading-relaxed text-slate-400">{signal.text}</p>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-slate-500">
        <span className="text-slate-300">{signal.source_name}</span>
        <span>{signal.source_type}</span>
        <ReliabilityBar value={signal.source_reliability} />
        <span>sev {signal.severity} · conf {pct(signal.confidence)}</span>
        {signal.url
          ? <a href={signal.url} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline">Open source ↗</a>
          : <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-300 ring-1 ring-amber-500/30">synthetic exercise source</span>}
      </div>

      <button onClick={() => setOpen((o) => !o)} className="mt-2 text-[11px] text-slate-400 hover:text-slate-200">
        {open ? '▾' : '▸'} AI analysis & links ({related.length})
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

export default function AlertDetail({ alert, loading }) {
  const [activeSignal, setActiveSignal] = useState(null)

  if (!alert) {
    return <div className="panel p-10 text-center text-slate-500">{loading ? 'Loading alert…' : 'Select an alert to see its evidence.'}</div>
  }

  const selectSignal = (id) => {
    setActiveSignal(id)
    document.getElementById(`ev-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  return (
    <div className="panel p-4 sm:p-5">
      <div className="flex flex-wrap items-start gap-5">
        <ScoreRing score={alert.score} levelName={alert.level} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <LevelBadge value={alert.level} />
            {alert.is_hybrid && <span className="rounded-md bg-fuchsia-500/15 px-2 py-0.5 text-[10px] font-bold tracking-widest text-fuchsia-300 ring-1 ring-fuchsia-500/40">HYBRID PATTERN</span>}
            {alert.synthetic && <span className="rounded-md bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300 ring-1 ring-amber-500/30">EXERCISE SCENARIO</span>}
            <span className="text-xs text-slate-500">confidence <span className="font-mono text-slate-200">{pct(alert.confidence)}</span></span>
          </div>
          <h2 className="mt-2 text-xl font-semibold text-slate-50">{alert.title}</h2>
          <p className="mt-1 text-sm text-slate-400">{alert.summary}</p>
          <div className="mt-3"><Sequence sequence={alert.sequence} firstSeen={alert.first_seen} /></div>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <SectionTitle right={<span className="text-[11px] text-slate-500">{alert.links.length} correlation links</span>}>Correlation timeline</SectionTitle>
          <CorrelationTimeline alert={alert} activeId={activeSignal} onSelectSignal={selectSignal} />
        </div>
        <div className="lg:col-span-2">
          <ScoreBreakdown breakdown={alert.breakdown} score={alert.score} />
        </div>
      </div>

      {alert.shared_entities.length > 0 && (
        <div className="mt-6">
          <SectionTitle>Linking entities</SectionTitle>
          <div className="flex flex-wrap gap-2">
            {alert.shared_entities.slice(0, 14).map((e) => (
              <span key={e.type + e.name} title={e.type} className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800/70 px-2.5 py-1 text-xs text-slate-200 ring-1 ring-slate-700">
                <span className="text-slate-500">{ENTITY_ICON[e.type] || '•'}</span>
                {e.name}
                <span className="rounded bg-slate-950 px-1 font-mono text-[10px] text-slate-400">×{e.count}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-6">
        <SectionTitle right={<span className="text-[11px] text-slate-500">{alert.signal_count} signals · {alert.source_count} sources</span>}>Source evidence</SectionTitle>
        <div className="space-y-2">
          {[...alert.signals].reverse().map((s) => (
            <Evidence key={s.id} signal={s} active={s.id === activeSignal} links={alert.links} />
          ))}
        </div>
      </div>
    </div>
  )
}
