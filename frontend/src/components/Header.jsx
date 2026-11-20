import { LANGS, useI18n } from '../lib/i18n'

const TABS = ['board', 'stats', 'signals', 'network', 'analyze', 'model']

function Logo() {
  return (
    <svg width="34" height="34" viewBox="0 0 32 32" aria-hidden>
      <circle cx="16" cy="16" r="14" fill="none" stroke="#22d3ee" strokeWidth="1.6" opacity="0.9" />
      <circle cx="16" cy="16" r="9" fill="none" stroke="#d946ef" strokeWidth="1.6" opacity="0.8" />
      <path d="M16 16 L16 2 A14 14 0 0 1 28.1 9 Z" fill="#22d3ee" opacity="0.18" />
      <circle cx="16" cy="16" r="2.6" fill="#ef4444" />
      <circle cx="22" cy="9" r="1.4" fill="#f59e0b" />
    </svg>
  )
}

const NAV_ICON = { board: '🛡️', stats: '📊', network: '🕸️', signals: '📰', analyze: '🔍', model: '🧠' }

/** Reopens the short "What is this page?" guide at any time. */
function HowButton() {
  const { t } = useI18n()
  return (
    <button
      onClick={() => { window.dispatchEvent(new Event('hs-guide')); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
      className="rounded-lg bg-cyan-500/10 px-2.5 py-1.5 text-xs font-medium text-cyan-200 ring-1 ring-cyan-500/30 hover:bg-cyan-500/20"
    >
      💡 <span className="hidden sm:inline">{t('how.btn')}</span>
    </button>
  )
}

function LangSwitch() {
  const { lang, setLang } = useI18n()
  return (
    <div className="flex rounded-lg bg-slate-900/80 p-0.5 ring-1 ring-slate-800" role="group" aria-label="Language">
      {LANGS.map(([code, label]) => (
        <button key={code} onClick={() => setLang(code)}
          className={`rounded-md px-2 py-1 font-mono text-[11px] ${lang === code ? 'bg-slate-700 text-white' : 'text-slate-500 hover:text-slate-300'}`}>
          {label}
        </button>
      ))}
    </div>
  )
}

/** Phone and tablet navigation: a fixed bar at the bottom, like mobile apps. */
export function BottomNav({ view, setView }) {
  const { t } = useI18n()
  return (
    <nav className="no-print fixed inset-x-0 bottom-0 z-[2000] grid grid-cols-6 border-t border-slate-800 bg-[#060a13]/95 backdrop-blur lg:hidden"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}>
      {TABS.map((key) => (
        <button key={key} onClick={() => { setView(key); window.scrollTo({ top: 0 }) }}
          className={`flex flex-col items-center gap-0.5 py-2 text-[11px] ${view === key ? 'text-cyan-300' : 'text-slate-400'}`}
          aria-current={view === key ? 'page' : undefined}>
          <span className="text-lg leading-none" aria-hidden>{NAV_ICON[key]}</span>
          {t(`nav.${key}`)}
        </button>
      ))}
    </nav>
  )
}

export default function Header({ view, setView, health, busy, onIngest }) {
  const { t } = useI18n()
  return (
    <header className="no-print border-b border-slate-800/80 bg-[#060a13]/90 backdrop-blur lg:sticky lg:top-0 lg:z-[2000]">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-3 py-2 sm:px-4 lg:py-3">
        <div className="flex items-center gap-2 sm:gap-3">
          <Logo />
          <div>
            <div className="text-base font-semibold tracking-wide text-slate-100 sm:text-[17px]">
              Hybrid<span className="text-cyan-300">Scope</span>
            </div>
            <div className="hidden text-[10px] uppercase tracking-[0.2em] text-slate-500 sm:block">{t('app.subtitle')}</div>
          </div>
        </div>

        <nav className="hidden gap-1 rounded-lg bg-slate-900/80 p-1 ring-1 ring-slate-800 lg:flex">
          {TABS.map((key) => (
            <button
              key={key}
              onClick={() => setView(key)}
              className={`rounded-md px-3 py-1.5 text-sm transition ${view === key ? 'bg-slate-700/70 text-white shadow' : 'text-slate-400 hover:text-slate-200'}`}
            >
              {t(`tab.${key}`)}
            </button>
          ))}
        </nav>

        <div className="ml-auto flex flex-wrap items-center justify-end gap-2 text-xs sm:gap-3">
          {health?.offline && (
            <span className="rounded-md bg-amber-500/15 px-2 py-1 font-mono text-[11px] font-semibold tracking-wider text-amber-300 ring-1 ring-amber-500/40" title={health.snapshot ? `snapshot ${health.snapshot.exported_at} · ${health.snapshot.signals} signals` : ''}>
              {t('hdr.offline')}
            </span>
          )}
          <HowButton />
          <LangSwitch />
          <button
            onClick={onIngest}
            disabled={!!busy}
            title={t('hdr.ingest')}
            aria-label={t('hdr.ingest')}
            className="rounded-lg bg-cyan-500/15 px-2.5 py-1.5 font-medium text-cyan-200 ring-1 ring-cyan-500/40 transition hover:bg-cyan-500/25 disabled:opacity-50 sm:px-3"
          >
            <span className={busy === 'ingest' ? 'inline-block animate-spin' : ''}>⟳</span>
            <span className="hidden sm:inline"> {busy === 'ingest' ? t('hdr.ingesting') : t('hdr.ingest')}</span>
          </button>
        </div>
      </div>
    </header>
  )
}
