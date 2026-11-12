export const CATEGORIES = {
  disinformation: { label: 'Disinformation', short: 'DISINFO', color: '#d946ef', text: 'text-fuchsia-300', bg: 'bg-fuchsia-500/15', ring: 'ring-fuchsia-500/40' },
  cyber: { label: 'Cyber', short: 'CYBER', color: '#22d3ee', text: 'text-cyan-300', bg: 'bg-cyan-500/15', ring: 'ring-cyan-500/40' },
  infrastructure: { label: 'Infrastructure', short: 'INFRA', color: '#f59e0b', text: 'text-amber-300', bg: 'bg-amber-500/15', ring: 'ring-amber-500/40' },
  physical: { label: 'Physical / Geopolitical', short: 'PHYSICAL', color: '#fb7185', text: 'text-rose-300', bg: 'bg-rose-500/15', ring: 'ring-rose-500/40' },
  other: { label: 'Not threat-relevant', short: 'OTHER', color: '#64748b', text: 'text-slate-400', bg: 'bg-slate-500/15', ring: 'ring-slate-500/40' },
}
export const CATEGORY_ORDER = ['disinformation', 'cyber', 'infrastructure', 'physical']
export const cat = (c) => CATEGORIES[c] || CATEGORIES.other

export const LEVELS = {
  CRITICAL: { color: '#ef4444', text: 'text-red-300', bg: 'bg-red-500/15', ring: 'ring-red-500/50' },
  HIGH: { color: '#f97316', text: 'text-orange-300', bg: 'bg-orange-500/15', ring: 'ring-orange-500/50' },
  MEDIUM: { color: '#eab308', text: 'text-yellow-300', bg: 'bg-yellow-500/15', ring: 'ring-yellow-500/50' },
  LOW: { color: '#64748b', text: 'text-slate-300', bg: 'bg-slate-500/15', ring: 'ring-slate-500/50' },
}
export const level = (l) => LEVELS[l] || LEVELS.LOW

export const ANALYZERS = {
  'claude-precomputed': { label: 'Claude (precomputed)', cls: 'text-violet-300 bg-violet-500/10 ring-violet-500/30' },
  'local-nlp': { label: 'Local NLP', cls: 'text-slate-300 bg-slate-500/10 ring-slate-500/30' },
}
export const analyzer = (a) =>
  ANALYZERS[a] || { label: a?.startsWith('llm:') ? `LLM · ${a.slice(4)}` : a, cls: 'text-emerald-300 bg-emerald-500/10 ring-emerald-500/30' }

export function timeAgo(iso) {
  const h = (Date.now() - new Date(iso).getTime()) / 36e5
  if (h < 1) return `${Math.max(1, Math.round(h * 60))}m ago`
  if (h < 48) return `${Math.round(h)}h ago`
  return `${Math.round(h / 24)}d ago`
}

export const fmtTime = (iso) =>
  new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })

export const pct = (x) => `${Math.round((x || 0) * 100)}%`
