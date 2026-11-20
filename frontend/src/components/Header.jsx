import { LANGS, useI18n } from '../lib/i18n'

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

/** Clean top bar: the logo (back to the start) on the home page, "← Back" and the page name everywhere else. */
export default function Header({ page, title, onHome, onBack, health, busy, onIngest }) {
  const { t } = useI18n()
  const home = page === 'home'
  return (
    <header className="no-print sticky top-0 z-[2000] border-b border-slate-800/80 bg-[#060a13]/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-3 py-2 sm:px-4">
        {home ? (
          <button onClick={onHome} className="flex items-center gap-2 sm:gap-3" aria-label="HybridScope">
            <Logo />
            <span className="text-left">
              <span className="block text-base font-semibold tracking-wide text-slate-100 sm:text-[17px]">
                Hybrid<span className="text-cyan-300">Scope</span>
              </span>
              <span className="hidden text-[10px] uppercase tracking-[0.2em] text-slate-500 sm:block">{t('app.subtitle')}</span>
            </span>
          </button>
        ) : (
          <div className="flex min-w-0 items-center gap-2">
            <button onClick={onBack} className="shrink-0 rounded-lg bg-slate-800/80 px-3 py-1.5 text-sm text-slate-200 ring-1 ring-slate-700 hover:bg-slate-700">
              ← {t('page.back')}
            </button>
            <span className="truncate text-sm font-semibold text-slate-100 sm:text-base">
              {t(`page.${page}`)}{title ? ` · ${title}` : ''}
            </span>
          </div>
        )}

        <div className="ml-auto flex shrink-0 items-center gap-2 text-xs">
          {health?.offline && (
            <span className="hidden rounded-md bg-amber-500/15 px-2 py-1 font-mono text-[11px] font-semibold tracking-wider text-amber-300 ring-1 ring-amber-500/40 sm:inline">
              {t('hdr.offline')}
            </span>
          )}
          <LangSwitch />
          <button
            onClick={onIngest}
            disabled={!!busy}
            title={t('hdr.ingest')}
            aria-label={t('hdr.ingest')}
            className="rounded-lg bg-cyan-500/15 px-2.5 py-1.5 font-medium text-cyan-200 ring-1 ring-cyan-500/40 transition hover:bg-cyan-500/25 disabled:opacity-50"
          >
            <span className={busy === 'ingest' ? 'inline-block animate-spin' : ''}>⟳</span>
            <span className="hidden md:inline"> {busy === 'ingest' ? t('hdr.ingesting') : t('hdr.ingest')}</span>
          </button>
        </div>
      </div>
    </header>
  )
}
