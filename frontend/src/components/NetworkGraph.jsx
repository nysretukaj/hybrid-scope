import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY } from 'd3-force'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../lib/api'
import { level } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { SectionTitle } from './ui'

const W = 1000
const H = 640
const TYPE_COLOR = { actor: '#fb7185', organisation: '#60a5fa', technology: '#22d3ee', CVE: '#f59e0b', narrative: '#e879f9' }

const radius = (n) => (n.kind === 'alert' ? 12 + n.score / 6 : 4 + Math.min(9, n.count * 1.1))

export default function NetworkGraph({ source, refreshKey, onOpenAlert }) {
  const { t } = useI18n()
  const [data, setData] = useState(null)
  const [, setFrame] = useState(0)
  const [hover, setHover] = useState(null)
  const nodesRef = useRef([])
  const linksRef = useRef([])
  const simRef = useRef(null)
  const svgRef = useRef(null)
  const dragRef = useRef(null)

  useEffect(() => {
    let alive = true
    api.graph(source).then((d) => alive && setData(d))
    return () => { alive = false }
  }, [source, refreshKey])

  useEffect(() => {
    if (!data) return
    const prev = new Map(nodesRef.current.map((n) => [n.id, n]))
    const nodes = data.nodes.map((n) => {
      const p = prev.get(n.id)
      return { ...n, x: p?.x ?? W / 2 + (Math.random() - 0.5) * 400, y: p?.y ?? H / 2 + (Math.random() - 0.5) * 300 }
    })
    const links = data.edges.map((e) => ({ ...e }))
    const sim = forceSimulation(nodes)
      .force('link', forceLink(links).id((d) => d.id).distance((l) => 40 + 30 / l.weight).strength(0.5))
      .force('charge', forceManyBody().strength((d) => (d.kind === 'alert' ? -650 : -70)))
      .force('center', forceCenter(W / 2, H / 2))
      .force('collide', forceCollide((d) => radius(d) + 5))
      .force('x', forceX(W / 2).strength(0.05))
      .force('y', forceY(H / 2).strength(0.08))
      .alpha(prev.size ? 0.3 : 1)
    sim.on('tick', () => {
      for (const n of nodes) {
        const r = radius(n)
        n.x = Math.max(r + 4, Math.min(W - r - 4, n.x))
        n.y = Math.max(r + 4, Math.min(H - r - 4, n.y))
      }
      setFrame((f) => f + 1)
    })
    nodesRef.current = nodes
    linksRef.current = links
    simRef.current = sim
    return () => sim.stop()
  }, [data])

  const neighbors = useMemo(() => {
    const m = new Map()
    for (const e of data?.edges || []) {
      if (!m.has(e.source)) m.set(e.source, new Set())
      if (!m.has(e.target)) m.set(e.target, new Set())
      m.get(e.source).add(e.target)
      m.get(e.target).add(e.source)
    }
    return m
  }, [data])

  const toSvg = (evt) => {
    const pt = svgRef.current.createSVGPoint()
    pt.x = evt.clientX
    pt.y = evt.clientY
    return pt.matrixTransform(svgRef.current.getScreenCTM().inverse())
  }

  const onPointerDown = (evt, n) => {
    evt.currentTarget.setPointerCapture?.(evt.pointerId)
    const p = toSvg(evt)
    dragRef.current = { n, sx: p.x, sy: p.y, moved: false }
    n.fx = n.x
    n.fy = n.y
    simRef.current?.alphaTarget(0.25).restart()
  }
  const onPointerMove = (evt) => {
    const d = dragRef.current
    if (!d) return
    const p = toSvg(evt)
    if (Math.hypot(p.x - d.sx, p.y - d.sy) > 3) d.moved = true
    d.n.fx = p.x
    d.n.fy = p.y
  }
  const onPointerUp = () => {
    const d = dragRef.current
    if (!d) return
    d.n.fx = null
    d.n.fy = null
    simRef.current?.alphaTarget(0)
    if (!d.moved && d.n.kind === 'alert') onOpenAlert(d.n.alert_id)
    dragRef.current = null
  }

  const nodes = nodesRef.current
  const links = linksRef.current
  const focus = hover ? new Set([hover, ...(neighbors.get(hover) || [])]) : null
  const bridges = (data?.nodes || []).filter((n) => n.kind === 'entity' && n.alerts >= 2).sort((a, b) => b.alerts - a.alerts || b.count - a.count)

  return (
    <div className="grid gap-4 p-4 xl:grid-cols-[1fr_300px]">
      <div className="panel overflow-hidden">
        <div className="border-b border-slate-800 px-4 py-3">
          <div className="text-sm font-semibold text-slate-100">{t('n.title')}</div>
          <div className="text-xs text-slate-500">{t('n.sub')}</div>
        </div>
        {data && data.nodes.length === 0 && <div className="p-10 text-center text-sm text-slate-500">{t('n.none')}</div>}
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="w-full touch-none select-none"
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerUp}
          role="img"
          aria-label={t('n.title')}
        >
          <defs>
            <radialGradient id="bg-glow" cx="50%" cy="50%" r="60%">
              <stop offset="0%" stopColor="#0f172a" />
              <stop offset="100%" stopColor="#060a13" />
            </radialGradient>
          </defs>
          <rect width={W} height={H} fill="url(#bg-glow)" />
          {links.map((l, k) => {
            const on = focus && focus.has(l.source.id) && focus.has(l.target.id)
            return (
              <line
                key={k}
                x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y}
                stroke={on ? '#e2e8f0' : '#334155'}
                strokeWidth={Math.min(4, 0.8 + l.weight * 0.5)}
                opacity={focus ? (on ? 0.9 : 0.08) : 0.5}
              />
            )
          })}
          {nodes.map((n) => {
            const r = radius(n)
            const dim = focus && !focus.has(n.id)
            const color = n.kind === 'alert' ? level(n.level).color : TYPE_COLOR[n.type] || '#94a3b8'
            const showLabel = n.kind === 'alert' || n.alerts >= 2 || n.count >= 4 || (focus && focus.has(n.id))
            return (
              <g
                key={n.id}
                transform={`translate(${n.x} ${n.y})`}
                opacity={dim ? 0.18 : 1}
                className="cursor-pointer"
                onPointerDown={(e) => onPointerDown(e, n)}
                onPointerEnter={() => setHover(n.id)}
                onPointerLeave={() => setHover(null)}
              >
                {n.kind === 'alert' ? (
                  <>
                    <circle r={r + 5} fill={color} opacity="0.15" />
                    <circle r={r} fill="#0b1220" stroke={color} strokeWidth={n.is_hybrid ? 3 : 1.5} strokeDasharray={n.is_hybrid ? null : '3 3'} />
                    <text textAnchor="middle" dy="4" fontSize="12" fontWeight="700" fill={color} fontFamily="JetBrains Mono">{Math.round(n.score)}</text>
                    <text textAnchor="middle" dy={r + 15} fontSize="12" fontWeight="600" fill="#e2e8f0" fontFamily="Inter">{n.label}</text>
                  </>
                ) : (
                  <>
                    <circle r={r} fill={color} fillOpacity="0.85" stroke="#060a13" strokeWidth="1.5" />
                    {showLabel && <text x={r + 4} dy="4" fontSize="10.5" fill="#cbd5e1" fontFamily="Inter">{n.label}</text>}
                  </>
                )}
                <title>{n.kind === 'alert' ? `${n.label} · ${n.level} ${Math.round(n.score)}` : `${t(`et.${n.type}`)}: ${n.label} · ${t('n.mentions', { n: n.count })} · ${t('n.alerts', { n: n.alerts })}`}</title>
              </g>
            )
          })}
        </svg>
      </div>

      <div className="space-y-4">
        <div className="panel p-4">
          <SectionTitle>{t('n.legend')}</SectionTitle>
          <div className="space-y-1.5 text-xs text-slate-300">
            {Object.entries(TYPE_COLOR).map(([type, color]) => (
              <div key={type} className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />{t(`et.${type}`)}
              </div>
            ))}
            <div className="flex items-center gap-2 pt-1 text-slate-400">
              <span className="h-3.5 w-3.5 rounded-full border-2 border-red-500" /> {t('n.alertNode')}
            </div>
          </div>
        </div>
        <div className="panel p-4">
          <SectionTitle>{t('n.bridges')}</SectionTitle>
          {bridges.length === 0 && <div className="text-xs text-slate-500">{t('n.none')}</div>}
          <ul className="space-y-1.5">
            {bridges.slice(0, 14).map((b) => (
              <li
                key={b.id}
                onPointerEnter={() => setHover(b.id)}
                onPointerLeave={() => setHover(null)}
                className="flex cursor-default items-center gap-2 rounded-md px-2 py-1 text-xs hover:bg-slate-800/60"
              >
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: TYPE_COLOR[b.type] }} />
                <span className="truncate text-slate-200">{b.label}</span>
                <span className="ml-auto whitespace-nowrap font-mono text-[10px] text-slate-500">{t('n.alerts', { n: b.alerts })}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
