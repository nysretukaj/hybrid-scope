// Formatting helpers. The active language is set by LangProvider (setFormatLang) so that
// relative times, dates, badges and analyzer names follow the selected language everywhere.
let LANG = 'en'
export const setFormatLang = (lang) => { LANG = lang }

const LOCALES = { en: 'en-GB', sq: 'sq-AL', de: 'de-DE' }

export const CATEGORIES = {
  disinformation: { color: '#d946ef', text: 'text-fuchsia-300', bg: 'bg-fuchsia-500/15', ring: 'ring-fuchsia-500/40' },
  political: { color: '#818cf8', text: 'text-indigo-300', bg: 'bg-indigo-500/15', ring: 'ring-indigo-500/40' },
  cyber: { color: '#22d3ee', text: 'text-cyan-300', bg: 'bg-cyan-500/15', ring: 'ring-cyan-500/40' },
  infrastructure: { color: '#f59e0b', text: 'text-amber-300', bg: 'bg-amber-500/15', ring: 'ring-amber-500/40' },
  physical: { color: '#fb7185', text: 'text-rose-300', bg: 'bg-rose-500/15', ring: 'ring-rose-500/40' },
  other: { color: '#64748b', text: 'text-slate-400', bg: 'bg-slate-500/15', ring: 'ring-slate-500/40' },
}
// "physical" is the Security category (the key is kept so stored data stays valid)
export const CATEGORY_ORDER = ['disinformation', 'political', 'cyber', 'infrastructure', 'physical']
export const cat = (c) => CATEGORIES[c] || CATEGORIES.other

export const SUBCATEGORIES = {
  cyber: ['ransomware', 'ddos', 'data_breach', 'phishing', 'espionage', 'intrusion', 'vulnerability', 'malware'],
  disinformation: ['fake_news', 'deepfake', 'bot_network', 'impersonation', 'coordinated_campaign', 'propaganda'],
  political: ['foreign_interference', 'election_interference', 'coercion', 'destabilization'],
  infrastructure: ['energy', 'water', 'transport', 'telecom', 'ics'],
  physical: ['terrorism', 'organized_crime', 'border', 'military', 'sabotage', 'unrest', 'violent_incident'],
}

const SHORT = {
  en: { disinformation: 'DISINFO', political: 'POLITICAL', cyber: 'CYBER', infrastructure: 'INFRA', physical: 'SECURITY', other: 'OTHER' },
  sq: { disinformation: 'DEZINFO', political: 'POLITIK', cyber: 'KIBER', infrastructure: 'INFRA', physical: 'SIGURI', other: 'TJETËR' },
  de: { disinformation: 'DESINFO', political: 'POLITIK', cyber: 'CYBER', infrastructure: 'INFRA', physical: 'SICHERHEIT', other: 'SONSTIGE' },
}

// low / medium / high bands (confidence, impact, urgency, evidence quality)
export const BAND_COLOR = { high: '#34d399', medium: '#eab308', low: '#f87171' }
// for impact and urgency "high" is the worrying end
export const RISK_BAND_COLOR = { high: '#f87171', medium: '#eab308', low: '#34d399' }
export const VERIFICATION = {
  unverified: { color: '#94a3b8', icon: '○' },
  investigating: { color: '#38bdf8', icon: '🔎' },
  partial: { color: '#eab308', icon: '◐' },
  confirmed: { color: '#34d399', icon: '✓' },
  disproved: { color: '#64748b', icon: '✗' },
}
/** How a cause reads: for disinformation "deliberate" means disinformation and "accidental" misinformation. */
export function causeLabel(t, cause, categories) {
  const onlyDisinfo = categories?.length === 1 && categories[0] === 'disinformation'
  if (onlyDisinfo && (cause === 'deliberate' || cause === 'accidental')) return t(`cause.dis.${cause}`)
  return t(`cause.${cause || 'unknown'}`)
}
export const VERIFICATION_ORDER =['unverified', 'investigating', 'partial', 'confirmed', 'disproved']
// thousands separators written out (Albanian locale data is often missing in browsers)
const THOUSANDS = { en: ',', sq: ' ', de: '.' }
export const fmtCount = (n) => (n == null ? null : String(n).replace(/\B(?=(\d{3})+(?!\d))/g, THOUSANDS[LANG] || ','))
export const catShort = (c) => SHORT[LANG]?.[c] || SHORT.en[c] || SHORT.en.other

export const LEVELS = {
  CRITICAL: { color: '#ef4444', text: 'text-red-300', bg: 'bg-red-500/15', ring: 'ring-red-500/50' },
  HIGH: { color: '#f97316', text: 'text-orange-300', bg: 'bg-orange-500/15', ring: 'ring-orange-500/50' },
  MEDIUM: { color: '#eab308', text: 'text-yellow-300', bg: 'bg-yellow-500/15', ring: 'ring-yellow-500/50' },
  LOW: { color: '#64748b', text: 'text-slate-300', bg: 'bg-slate-500/15', ring: 'ring-slate-500/50' },
}
export const level = (l) => LEVELS[l] || LEVELS.LOW

const LEVEL_LABELS = {
  en: { CRITICAL: 'CRITICAL', HIGH: 'HIGH', MEDIUM: 'MEDIUM', LOW: 'LOW' },
  sq: { CRITICAL: 'KRITIK', HIGH: 'I LARTË', MEDIUM: 'MESATAR', LOW: 'I ULËT' },
  de: { CRITICAL: 'KRITISCH', HIGH: 'HOCH', MEDIUM: 'MITTEL', LOW: 'NIEDRIG' },
}
export const levelLabel = (l) => LEVEL_LABELS[LANG]?.[l] || l

const ANALYZER_LABELS = {
  'claude-precomputed': { en: 'Claude (precomputed)', sq: 'Claude (i parallogaritur)', de: 'Claude (vorberechnet)' },
  'local-nlp': { en: 'Local NLP', sq: 'NLP lokal', de: 'Lokales NLP' },
  analyst: { en: 'Corrected by analyst', sq: 'Korrigjuar nga analisti', de: 'Vom Analysten korrigiert' },
}
const CONNECTING = { en: 'connecting…', sq: 'po lidhet…', de: 'verbinde…' }
const ANALYZER_CLS = {
  'claude-precomputed': 'text-violet-300 bg-violet-500/10 ring-violet-500/30',
  'local-nlp': 'text-slate-300 bg-slate-500/10 ring-slate-500/30',
  analyst: 'text-amber-200 bg-amber-500/10 ring-amber-500/30',
}
export const analyzer = (a) => {
  if (ANALYZER_LABELS[a]) return { label: ANALYZER_LABELS[a][LANG] || ANALYZER_LABELS[a].en, cls: ANALYZER_CLS[a] }
  const model = a?.startsWith('llm:') ? a.slice(4) : a
  return {
    label: `LLM · ${model === '(connecting)' ? CONNECTING[LANG] : model}`,
    cls: 'text-emerald-300 bg-emerald-500/10 ring-emerald-500/30',
  }
}

const AGO = {
  en: { m: (n) => `${n}m ago`, h: (n) => `${n}h ago`, d: (n) => `${n}d ago` },
  sq: { m: (n) => `para ${n} min`, h: (n) => `para ${n} orësh`, d: (n) => `para ${n} ditësh` },
  de: { m: (n) => `vor ${n} Min.`, h: (n) => `vor ${n} Std.`, d: (n) => `vor ${n} T.` },
}
export function timeAgo(iso) {
  const f = AGO[LANG] || AGO.en
  const h = (Date.now() - new Date(iso).getTime()) / 36e5
  if (h < 1) return f.m(Math.max(1, Math.round(h * 60)))
  if (h < 48) return f.h(Math.round(h))
  return f.d(Math.round(h / 24))
}

// Albanian month names written out: many browsers ship without Albanian locale data and would fall back to English.
const SQ_MONTHS = ['jan', 'shk', 'mar', 'pri', 'maj', 'qer', 'korr', 'gush', 'sht', 'tet', 'nën', 'dhj']
const pad2 = (n) => String(n).padStart(2, '0')

export const fmtTime = (iso) => {
  const d = new Date(iso)
  if (LANG === 'sq') return `${d.getDate()} ${SQ_MONTHS[d.getMonth()]}, ${pad2(d.getHours())}:${pad2(d.getMinutes())}`
  return d.toLocaleString(LOCALES[LANG] || 'en-GB', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export const pct = (x) => `${Math.round((x || 0) * 100)}%`
