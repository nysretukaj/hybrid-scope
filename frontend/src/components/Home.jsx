import { useI18n } from '../lib/i18n'
import { StatusBanner } from './StatusBanner'

const TILES = [
  { page: 'alerts', icon: '🛡️', accent: '#f87171' },
  { page: 'map', icon: '🗺️', accent: '#38bdf8' },
  { page: 'stats', icon: '📊', accent: '#a78bfa' },
  { page: 'news', icon: '📰', accent: '#22d3ee' },
  { page: 'analyze', icon: '🔍', accent: '#34d399' },
  { page: 'network', icon: '🕸️', accent: '#e879f9' },
]

/** Start page: one sentence about the situation, then big buttons. Nothing else until you tap. */
export function Home({ alerts, stats, onGo, onOpenAlert }) {
  const { t } = useI18n()
  const critical = alerts.filter((a) => a.level === 'CRITICAL').length
  const sub = {
    alerts: t('home.alertsSub', { n: alerts.length, c: critical }),
    map: t('home.mapSub'),
    stats: t('home.statsSub'),
    news: t('home.newsSub', { n: stats?.signals_total ?? '…' }),
    analyze: t('home.analyzeSub'),
    network: t('home.networkSub'),
  }
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <StatusBanner alerts={alerts} onOpen={onOpenAlert} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {TILES.map((tile) => (
          <button key={tile.page} onClick={() => onGo(`/${tile.page}`)}
            className="group panel flex min-h-[112px] flex-col items-start gap-1 p-4 text-left transition hover:-translate-y-0.5 hover:ring-slate-500 active:translate-y-0"
            style={{ boxShadow: `inset 0 3px 0 ${tile.accent}` }}>
            <span className="text-3xl leading-none" aria-hidden>{tile.icon}</span>
            <span className="mt-2 text-base font-semibold text-slate-100">{t(`page.${tile.page}`)}</span>
            <span className="text-xs leading-snug text-slate-400">{sub[tile.page]}</span>
          </button>
        ))}
      </div>

      <button onClick={() => onGo('/help')}
        className="flex w-full items-center gap-3 rounded-xl bg-cyan-500/10 px-4 py-3 text-left ring-1 ring-cyan-500/30 hover:bg-cyan-500/15">
        <span className="text-2xl" aria-hidden>💡</span>
        <span>
          <span className="block font-semibold text-cyan-100">{t('page.help')}</span>
          <span className="block text-xs text-slate-400">{t('home.helpSub')}</span>
        </span>
        <span className="ml-auto text-slate-500">›</span>
      </button>
    </div>
  )
}

const GLOSSARY = ['hybrid', 'score', 'confidence', 'verification', 'evidence', 'signal', 'sources', 'replay', 'brief']

/** Plain explanation of the system and of every term used on the pages. */
export function HelpPage() {
  const { t } = useI18n()
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <section className="panel p-5">
        <h2 className="text-lg font-semibold text-slate-50">{t('ob.title')}</h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-300">{t('ob.what')}</p>
        <ol className="mt-4 space-y-3">
          {[1, 2, 3].map((i) => (
            <li key={i} className="flex gap-3 text-sm leading-relaxed text-slate-300">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-cyan-500/25 text-xs font-bold text-cyan-100">{i}</span>
              <span>{t(`ob.${i}`)}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="panel p-5">
        <h2 className="text-lg font-semibold text-slate-50">{t('help.words')}</h2>
        <dl className="mt-3 divide-y divide-slate-800">
          {GLOSSARY.map((term) => (
            <div key={term} className="py-3">
              <dt className="text-sm font-semibold text-slate-100">{t(`help.term.${term}`)}</dt>
              <dd className="mt-1 text-sm leading-relaxed text-slate-400">{t(`h.${term}`)}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  )
}
