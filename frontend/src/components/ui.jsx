import { analyzer, cat, level } from '../lib/format'

export function CategoryBadge({ category, small }) {
  const c = cat(category)
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 font-mono font-semibold ring-1 ${c.bg} ${c.text} ${c.ring} ${small ? 'text-[9px]' : 'text-[10px]'} tracking-wider`}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: c.color }} />
      {c.short}
    </span>
  )
}

export function LevelBadge({ value }) {
  const l = level(value)
  return (
    <span className={`rounded-md px-2 py-0.5 font-mono text-[10px] font-bold tracking-widest ring-1 ${l.bg} ${l.text} ${l.ring}`}>
      {value}
    </span>
  )
}

export function AnalyzerBadge({ value }) {
  const a = analyzer(value)
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ring-1 ${a.cls}`}>{a.label}</span>
}

export function Chip({ children, title, className = '' }) {
  return (
    <span title={title} className={`inline-flex items-center rounded-md bg-slate-800/80 px-2 py-0.5 text-[11px] text-slate-300 ring-1 ring-slate-700 ${className}`}>
      {children}
    </span>
  )
}

export function SectionTitle({ children, right }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-2">
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{children}</h3>
      {right}
    </div>
  )
}

export function ReliabilityBar({ value }) {
  const color = value >= 0.8 ? '#34d399' : value >= 0.55 ? '#eab308' : '#f87171'
  return (
    <span className="inline-flex items-center gap-1.5" title={`Source reliability ${Math.round(value * 100)}%`}>
      <span className="h-1.5 w-12 overflow-hidden rounded-full bg-slate-800">
        <span className="block h-full rounded-full" style={{ width: `${value * 100}%`, background: color }} />
      </span>
      <span className="font-mono text-[10px] text-slate-400">{Math.round(value * 100)}</span>
    </span>
  )
}

export function ScoreRing({ score, levelName, size = 88 }) {
  const r = size / 2 - 7
  const c = 2 * Math.PI * r
  const color = level(levelName).color
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#1e293b" strokeWidth="7" />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="7" strokeLinecap="round"
        strokeDasharray={`${(score / 100) * c} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ filter: `drop-shadow(0 0 6px ${color}88)` }}
      />
      <text x="50%" y="48%" textAnchor="middle" dominantBaseline="middle" fill="#f1f5f9" fontSize={size * 0.28} fontWeight="700" fontFamily="JetBrains Mono, monospace">
        {Math.round(score)}
      </text>
      <text x="50%" y="70%" textAnchor="middle" fill="#64748b" fontSize={size * 0.11} fontFamily="Inter">RISK</text>
    </svg>
  )
}
