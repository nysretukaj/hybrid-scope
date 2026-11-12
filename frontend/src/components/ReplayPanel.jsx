import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { cat, fmtTime, level } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { CategoryBadge, LevelBadge, ScoreRing } from './ui'

const W = 640
const H = 170
const PAD = { l: 34, r: 14, t: 12, b: 26 }
const STEP_MS = 1300

export default function ReplayPanel({ alertId, source, onFrame, onClose }) {
  const { t } = useI18n()
  const [data, setData] = useState(null)
  const [i, setI] = useState(0)
  const [playing, setPlaying] = useState(true)

  useEffect(() => {
    let alive = true
    api.replay(alertId, source).then((d) => alive && (setData(d), setI(0), setPlaying(true)))
    return () => { alive = false }
  }, [alertId, source])

  useEffect(() => {
    if (!data || !playing) return
    if (i >= data.frames.length - 1) { setPlaying(false); return }
    const id = setTimeout(() => setI((x) => x + 1), STEP_MS)
    return () => clearTimeout(id)
  }, [data, playing, i])

  useEffect(() => { if (data) onFrame(data.frames[i]) }, [data, i, onFrame])
  useEffect(() => () => onFrame(null), [onFrame])

  const geo = useMemo(() => {
    if (!data) return null
    const ts = data.frames.map((f) => new Date(f.t).getTime())
    const t0 = Math.min(...ts)
    const t1 = Math.max(...ts) === t0 ? t0 + 36e5 : Math.max(...ts)
    const x = (t) => PAD.l + ((t - t0) / (t1 - t0)) * (W - PAD.l - PAD.r)
    const y = (s) => PAD.t + (1 - s / 100) * (H - PAD.t - PAD.b)
    return { x, y, pts: data.frames.map((f, k) => ({ x: x(ts[k]), y: y(f.score), f })) }
  }, [data])

  if (!data || !geo) return <div className="mt-4 rounded-lg bg-slate-950/60 p-6 text-center text-sm text-slate-500 ring-1 ring-slate-800">…</div>

  const frame = data.frames[i]
  const m = data.milestones
  const shown = geo.pts.slice(0, i + 1)
  const path = shown.map((p, k) => (k === 0 ? `M ${p.x} ${p.y}` : `H ${p.x} V ${p.y}`)).join(' ')
  const hybridIdx = m.first_hybrid ? data.frames.findIndex((f) => f.signal_id === m.first_hybrid.signal_id) : -1
  const impactIdx = m.impact ? data.frames.findIndex((f) => f.signal_id === m.impact.signal_id) : -1
  const showLead = impactIdx >= 0 && i >= impactIdx
  const lead = m.first_hybrid?.lead_hours

  return (
    <div className="mt-4 rounded-xl bg-slate-950/70 p-4 ring-1 ring-fuchsia-500/30">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="mr-auto text-[11px] font-semibold uppercase tracking-[0.16em] text-fuchsia-300">{t('rp.title')}</span>
        <button onClick={() => setPlaying((p) => !p)} className="rounded-md bg-slate-800 px-3 py-1 text-xs text-slate-200 ring-1 ring-slate-700 hover:bg-slate-700">
          {playing ? `❚❚ ${t('rp.pause')}` : `▶ ${t('rp.play')}`}
        </button>
        <button onClick={() => { setI(0); setPlaying(true) }} className="rounded-md px-3 py-1 text-xs text-slate-400 ring-1 ring-slate-700 hover:text-slate-200">↺ {t('rp.restart')}</button>
        <button onClick={onClose} className="rounded-md px-2 py-1 text-xs text-slate-500 hover:text-slate-200" aria-label={t('rp.close')}>✕</button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
        <div>
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Risk score over time">
            {[[75, 'CRITICAL'], [55, 'HIGH'], [35, 'MEDIUM']].map(([s, name]) => (
              <g key={s}>
                <line x1={PAD.l} x2={W - PAD.r} y1={geo.y(s)} y2={geo.y(s)} stroke={level(name).color} strokeOpacity="0.35" strokeDasharray="3 4" />
                <text x={PAD.l - 6} y={geo.y(s) + 3} textAnchor="end" fontSize="9" fill={level(name).color} fontFamily="JetBrains Mono">{s}</text>
              </g>
            ))}
            {impactIdx >= 0 && i >= impactIdx && (
              <g>
                <line x1={geo.pts[impactIdx].x} x2={geo.pts[impactIdx].x} y1={PAD.t} y2={H - PAD.b} stroke="#f59e0b" strokeWidth="1.5" />
                <text x={geo.pts[impactIdx].x + 4} y={PAD.t + 10} fontSize="10" fill="#fbbf24" fontFamily="Inter">⚡ {t('rp.impact')}</text>
              </g>
            )}
            {hybridIdx >= 0 && i >= hybridIdx && (
              <g>
                <line x1={geo.pts[hybridIdx].x} x2={geo.pts[hybridIdx].x} y1={PAD.t} y2={H - PAD.b} stroke="#e879f9" strokeWidth="1.5" strokeDasharray="4 3" />
                <text x={geo.pts[hybridIdx].x + 4} y={H - PAD.b - 6} fontSize="10" fill="#f0abfc" fontFamily="Inter">★ {t('rp.hybridAt')}</text>
              </g>
            )}
            {hybridIdx >= 0 && impactIdx > hybridIdx && i >= impactIdx && (
              <g>
                <line x1={geo.pts[hybridIdx].x} x2={geo.pts[impactIdx].x} y1={H - PAD.b + 12} y2={H - PAD.b + 12} stroke="#f0abfc" strokeWidth="1.5" markerEnd="url(#arr)" />
                <text x={(geo.pts[hybridIdx].x + geo.pts[impactIdx].x) / 2} y={H - PAD.b + 9} textAnchor="middle" fontSize="10" fill="#f0abfc" fontFamily="JetBrains Mono">+{lead}h</text>
              </g>
            )}
            <defs>
              <marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto">
                <path d="M0 0 L8 4 L0 8 z" fill="#f0abfc" />
              </marker>
            </defs>
            <path d={path} fill="none" stroke={level(frame.level).color} strokeWidth="2.5" style={{ transition: 'stroke 0.4s' }} />
            {shown.map((p, k) => (
              <circle key={k} cx={p.x} cy={p.y} r={k === i ? 6 : 3.5} fill={cat(p.f.category).color} stroke="#060a13" strokeWidth="1.5">
                <title>{p.f.title}</title>
              </circle>
            ))}
          </svg>
        </div>

        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <ScoreRing score={frame.score} levelName={frame.level} size={76} />
            <div className="space-y-1.5">
              <LevelBadge value={frame.level} />
              {frame.is_hybrid && <div><span className="animate-pulse rounded-md bg-fuchsia-500/20 px-2 py-0.5 text-[10px] font-bold tracking-widest text-fuchsia-200 ring-1 ring-fuchsia-500/50">HYBRID</span></div>}
              <div className="font-mono text-[10px] text-slate-500">{t('rp.signal', { i: i + 1, n: data.frames.length })}</div>
            </div>
          </div>
          <div key={frame.signal_id} className="rounded-lg bg-slate-900/80 p-2.5 ring-1 ring-slate-800" style={{ animation: 'fade-in .4s ease-out' }}>
            <div className="flex items-center gap-2 text-[10px] text-slate-500">
              <CategoryBadge category={frame.category} small />
              <span className="font-mono">{fmtTime(frame.t)}</span>
            </div>
            <div className="mt-1 text-xs font-medium leading-snug text-slate-100">{frame.title}</div>
            <div className="mt-0.5 text-[10px] text-slate-500">{frame.source}</div>
          </div>
        </div>
      </div>

      {showLead && (
        <div className="mt-3 flex items-center gap-4 rounded-lg bg-gradient-to-r from-fuchsia-500/15 to-amber-500/10 p-3 ring-1 ring-fuchsia-500/40" style={{ animation: 'fade-in .5s ease-out' }}>
          {lead > 0 ? (
            <>
              <div className="font-mono text-4xl font-bold text-fuchsia-200">{lead}h</div>
              <div className="text-sm text-slate-200">
                <div className="font-semibold">{t('rp.lead', { h: lead })}</div>
                <div className="text-xs text-slate-400">⚡ {m.impact.title}{m.first_high?.lead_hours > 0 ? ` · ${t('rp.leadHigh', { h: m.first_high.lead_hours })}` : ''}</div>
              </div>
            </>
          ) : (
            <div className="text-sm text-slate-300">{t('rp.noLead')}</div>
          )}
        </div>
      )}
    </div>
  )
}
