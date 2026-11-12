import { analyzer, timeAgo } from '../lib/format'
import { LANGS, useI18n } from '../lib/i18n'

const TABS = ['board', 'network', 'signals', 'analyze']

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

export default function Header({ view, setView, health, busy, onIngest, onReset }) {
  const { t, lang, setLang } = useI18n()
  const last = health?.last_ingest
  return (
    <header className="no-print sticky top-0 z-[2000] border-b border-slate-800/80 bg-[#060a13]/90 backdrop-blur">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3">
        <div className="flex items-center gap-3">
          <Logo />
          <div>
            <div className="text-[17px] font-semibold tracking-wide text-slate-100">
              Hybrid<span className="text-cyan-300">Scope</span>
            </div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">{t('app.subtitle')}</div>
          </div>
        </div>

        <nav className="flex gap-1 rounded-lg bg-slate-900/80 p-1 ring-1 ring-slate-800">
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

        <div className="ml-auto flex flex-wrap items-center gap-3 text-xs">
          {health?.offline && (
            <span className="rounded-md bg-amber-500/15 px-2 py-1 font-mono text-[11px] font-semibold tracking-wider text-amber-300 ring-1 ring-amber-500/40" title={health.snapshot ? `snapshot ${health.snapshot.exported_at} · ${health.snapshot.signals} signals` : ''}>
              {t('hdr.offline')}
            </span>
          )}
          <span className="flex items-center gap-2 text-slate-400">
            <span className="relative inline-block h-2 w-2 rounded-full text-emerald-400 live-dot" style={{ background: 'currentColor' }} />
            {t('hdr.analyzer')}: <span className="text-slate-200">{health ? analyzer(health.analyzer).label : '-'}</span>
          </span>
          {health?.llm?.enrich?.running && (
            <span className="rounded-md bg-emerald-500/10 px-2 py-1 font-mono text-[11px] text-emerald-300 ring-1 ring-emerald-500/30" title={health.llm.model_live}>
              {t('hdr.aiUpgrading', { done: health.llm.enrich.done, n: health.llm.enrich.queued })}
            </span>
          )}
          {health?.llm?.last_error && !health?.llm?.enrich?.running && (
            <span className="max-w-56 truncate text-[11px] text-amber-400" title={health.llm.last_error}>⚠ LLM: {health.llm.last_error}</span>
          )}
          <span className="hidden text-slate-500 xl:inline">
            {t('hdr.liveIngest')}: {last ? `${timeAgo(last.finished_at)} · ${last.fetched} ${t('hdr.items')}` : t('hdr.notRun')}
          </span>
          <div className="flex rounded-lg bg-slate-900/80 p-0.5 ring-1 ring-slate-800" role="group" aria-label="Language">
            {LANGS.map(([code, label]) => (
              <button
                key={code}
                onClick={() => setLang(code)}
                className={`rounded-md px-2 py-1 font-mono text-[11px] ${lang === code ? 'bg-slate-700 text-white' : 'text-slate-500 hover:text-slate-300'}`}
              >
                {label}
              </button>
            ))}
          </div>
          <button
            onClick={onIngest}
            disabled={!!busy}
            className="rounded-lg bg-cyan-500/15 px-3 py-1.5 font-medium text-cyan-200 ring-1 ring-cyan-500/40 transition hover:bg-cyan-500/25 disabled:opacity-50"
          >
            {busy === 'ingest' ? t('hdr.ingesting') : t('hdr.ingest')}
          </button>
          <button
            onClick={onReset}
            disabled={!!busy}
            className="rounded-lg px-3 py-1.5 text-slate-400 ring-1 ring-slate-700 transition hover:text-slate-200 disabled:opacity-50"
            title={t('hdr.resetTitle')}
          >
            {busy === 'reset' ? t('hdr.resetting') : t('hdr.reset')}
          </button>
        </div>
      </div>
    </header>
  )
}
