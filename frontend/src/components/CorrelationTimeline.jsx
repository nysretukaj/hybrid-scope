import { useMemo, useState } from 'react'
import { CATEGORY_ORDER, cat, fmtTime } from '../lib/format'
import { useI18n } from '../lib/i18n'

const W = 960
const LANE_H = 46
const TOP = 14
const LEFT = 128
const RIGHT = 24

export default function CorrelationTimeline({ alert, activeId, onSelectSignal, cutoff }) {
  const { t } = useI18n()
  const [hover, setHover] = useState(null)
  const cutoffMs = cutoff ? new Date(cutoff).getTime() : null
  const visible = (id) => cutoffMs == null || new Date(pos[id]?.s.timestamp).getTime() <= cutoffMs
  const lanes = CATEGORY_ORDER
  const H = TOP + lanes.length * LANE_H + 34

  const { pos, ticks } = useMemo(() => {
    const times = alert.signals.map((s) => new Date(s.timestamp).getTime())
    let t0 = Math.min(...times)
    let t1 = Math.max(...times)
    if (t1 - t0 < 36e5) { t0 -= 18e5; t1 += 18e5 }
    const pad = (t1 - t0) * 0.04
    t0 -= pad; t1 += pad
    const x = (t) => LEFT + ((t - t0) / (t1 - t0)) * (W - LEFT - RIGHT)
    const pos = {}
    alert.signals.forEach((s) => {
      const lane = Math.max(0, lanes.indexOf(s.category))
      pos[s.id] = { x: x(new Date(s.timestamp).getTime()), y: TOP + lane * LANE_H + LANE_H / 2, s }
    })
    // nudge overlapping nodes in the same lane
    const byLane = {}
    Object.values(pos).forEach((p) => (byLane[p.y] ||= []).push(p))
    Object.values(byLane).forEach((arr) => {
      arr.sort((a, b) => a.x - b.x)
      arr.forEach((p, i) => { if (i > 0 && p.x - arr[i - 1].x < 14) p.y += (i % 2 ? -9 : 9) })
    })
    const ticks = Array.from({ length: 6 }, (_, i) => {
      const t = t0 + ((t1 - t0) * i) / 5
      return { x: x(t), label: fmtTime(new Date(t).toISOString()) }
    })
    return { pos, ticks }
  }, [alert, lanes])

  const focus = hover || activeId
  const focusLinks = new Set(
    alert.links.filter((l) => l.source === focus || l.target === focus).flatMap((l) => [l.source, l.target]),
  )
  const hovered = hover ? pos[hover]?.s : null

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Correlation timeline">
        {lanes.map((c, i) => (
          <g key={c}>
            <rect x={LEFT - 6} y={TOP + i * LANE_H + 3} width={W - LEFT - RIGHT + 12} height={LANE_H - 6} rx="6" fill={cat(c).color} opacity={alert.categories.includes(c) ? 0.06 : 0.02} />
            <text x={LEFT - 14} y={TOP + i * LANE_H + LANE_H / 2 + 4} textAnchor="end" fontSize="11" fill={alert.categories.includes(c) ? cat(c).color : '#475569'} fontFamily="Inter" fontWeight="600">
              {t(`cat.${c}`).split(' ')[0]}
            </text>
          </g>
        ))}
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={t.x} x2={t.x} y1={TOP} y2={TOP + lanes.length * LANE_H} stroke="#1e293b" strokeDasharray="2 4" />
            <text x={t.x} y={H - 10} textAnchor="middle" fontSize="10" fill="#64748b" fontFamily="Inter">{t.label}</text>
          </g>
        ))}

        {alert.links.map((l) => {
          const a = pos[l.source]
          const b = pos[l.target]
          if (!a || !b || !visible(l.source) || !visible(l.target)) return null
          const on = focus && (l.source === focus || l.target === focus)
          const cross = a.s.category !== b.s.category
          const midX = (a.x + b.x) / 2
          const bend = a.y === b.y ? -22 : 0
          return (
            <path
              key={`${l.source}-${l.target}`}
              d={`M ${a.x} ${a.y} Q ${midX} ${(a.y + b.y) / 2 + bend} ${b.x} ${b.y}`}
              fill="none"
              stroke={l.kind === 'entity' ? (cross ? '#e879f9' : '#94a3b8') : '#475569'}
              strokeWidth={on ? 2 : l.kind === 'entity' ? 1.2 : 0.8}
              strokeDasharray={l.kind === 'temporal' ? '3 4' : null}
              opacity={focus ? (on ? 0.95 : 0.08) : l.kind === 'entity' ? 0.45 : 0.25}
            >
              <title>{l.reasons.join('\n')}</title>
            </path>
          )
        })}

        {Object.values(pos).filter(({ s }) => visible(s.id)).map(({ x, y, s }) => {
          const r = 5 + s.severity * 7
          const dim = focus && focus !== s.id && !focusLinks.has(s.id)
          return (
            <g
              key={s.id}
              transform={`translate(${x} ${y})`}
              className="cursor-pointer"
              onMouseEnter={() => setHover(s.id)}
              onMouseLeave={() => setHover(null)}
              onClick={() => onSelectSignal(s.id)}
              opacity={dim ? 0.25 : 1}
            >
              {activeId === s.id && <circle r={r + 5} fill="none" stroke="#f8fafc" strokeWidth="1.5" />}
              <circle r={r} fill={cat(s.category).color} fillOpacity="0.85" stroke="#060a13" strokeWidth="1.5" />
            </g>
          )
        })}
      </svg>
      {hovered && (
        <div className="pointer-events-none absolute right-2 top-2 max-w-xs rounded-lg bg-slate-950/95 p-2.5 text-xs ring-1 ring-slate-700">
          <div className="font-medium text-slate-100">{hovered.title}</div>
          <div className="mt-1 text-slate-400">{hovered.source_name} · {fmtTime(hovered.timestamp)}</div>
          <div className="mt-1 text-slate-500">severity {hovered.severity} · reliability {hovered.source_reliability}</div>
        </div>
      )}
      <div className="mt-1 flex flex-wrap gap-4 text-[10px] text-slate-500">
        <span><span className="text-fuchsia-300">━</span> {t('tl.cross')}</span>
        <span><span className="text-slate-400">━</span> {t('tl.same')}</span>
        <span><span className="text-slate-500">┄</span> {t('tl.temporal')}</span>
        <span>{t('tl.hint')}</span>
      </div>
    </div>
  )
}
