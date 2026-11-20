import { useCallback, useEffect, useRef, useState } from 'react'
import AlertDetail from './components/AlertDetail'
import AlertList from './components/AlertList'
import AnalyzePanel from './components/AnalyzePanel'
import Filters from './components/Filters'
import Header from './components/Header'
import { HelpPage, Home } from './components/Home'
import NetworkGraph from './components/NetworkGraph'
import SignalStream from './components/SignalStream'
import StatsPanel from './components/StatsPanel'
import ThreatMap from './components/ThreatMap'
import { api } from './lib/api'
import { useI18n } from './lib/i18n'

const POLL_MS = 30000
const PAGES =['alerts', 'map', 'stats', 'news', 'analyze', 'network', 'help']

/** Pages live in the address (#/alerts, #/alert/<id>), so the phone's Back button works too. */
function parseRoute() {
  const hash = window.location.hash
  const legacy = hash.match(/alert=([\w-]+)/) // links shared before the menu existed
  if (legacy) return { page: 'alert', id: legacy[1] }
  const [, page, id] = hash.match(/^#\/([\w-]+)(?:\/([\w-]+))?/) || []
  if (page === 'alert' && id) return { page: 'alert', id }
  return { page: PAGES.includes(page) ? page : 'home' }
}

export default function App() {
  const { t, lang } = useI18n()
  const [route, setRoute] = useState(parseRoute)
  const internalNavs = useRef(0)
  // hours: 0 = the whole 10-day window
  const [filters, setFilters] = useState({ q: '', category: '', zone: '', source: 'all', hours: 0, min_confidence: 0, hybrid_only: false, hide_dismissed: false })
  const [data, setData] = useState({ alerts: [], zones: [], total: 0 })
  const [stats, setStats] = useState(null)
  const [health, setHealth] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailState, setDetailState] = useState('idle') // idle | loading | missing
  const [tick, setTick] = useState(0)
  const [busy, setBusy] = useState(null)
  const [toast, setToast] = useState(null)
  const [error, setError] = useState(null)
  const alertId = route.page === 'alert' ? route.id : null

  useEffect(() => {
    const onHash = () => { setRoute(parseRoute()); window.scrollTo({ top: 0 }) }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const go = (path) => {
    internalNavs.current += 1
    window.location.hash = path
  }
  const back = () => {
    if (internalNavs.current > 0) { internalNavs.current -= 1; window.history.back() } else go('/')
  }
  const openAlert = (id) => go(`/alert/${id}`)

  const refresh = useCallback(async () => {
    try {
      const [a, s, h] = await Promise.all([api.alerts(filters, lang), api.stats(filters.source, filters.hours, lang), api.health()])
      setData(a)
      setStats(s)
      setHealth(h)
      setError(null)
      setTick((x) => x + 1)
    } catch (e) {
      setError(e.message)
    }
  }, [filters, lang])

  const enriching = !!health?.llm?.enrich?.running
  useEffect(() => {
    refresh()
    // poll faster while the LLM is upgrading live signals, so the pages visibly update
    const id = setInterval(refresh, enriching ? 6000 : POLL_MS)
    return () => clearInterval(id)
  }, [refresh, enriching])

  useEffect(() => {
    if (!alertId) { setDetail(null); setDetailState('idle'); return }
    let alive = true
    setDetailState((s) => (detail?.id === alertId ? s : 'loading'))
    api.alert(alertId, filters.source, lang)
      .then((d) => { if (alive) { setDetail(d); setDetailState('idle') } })
      .catch(() => { if (alive) { setDetail(null); setDetailState('missing') } })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [alertId, filters.source, tick, lang])

  const notify = (msg, kind = 'ok') => {
    setToast({ msg, kind })
    setTimeout(() => setToast(null), 6000)
  }

  const onIngest = async () => {
    setBusy('ingest')
    try {
      const r = await api.ingest()
      if (r.cooldown) {
        notify(t('t.cooldown'))
        await refresh()
        return
      }
      const failed = r.sources.filter((s) => !s.ok).map((s) => s.source)
      notify(t('t.ingest', { f: r.fetched, i: r.inserted, r: r.threat_relevant }) + (failed.length ? ` · ${t('t.failed')}: ${failed.join(', ')}` : ''), failed.length ? 'warn' : 'ok')
      await refresh()
    } catch (e) {
      notify(e.message, 'err')
    } finally {
      setBusy(null)
    }
  }

  const onFeedback = async (verdict, note) => {
    try {
      const r = await api.feedback(alertId, filters.source, verdict, note)
      notify(t('t.verification', { s: t(`v.${r.verification}`) }))
      await refresh()
    } catch (e) {
      notify(e.message, 'err')
    }
  }

  const onReclassify = async (signalId, category, subcategory) => {
    try {
      await api.classify(signalId, category, subcategory)
      notify(t('t.reclass', { c: t(`cat.${category}`) }))
      await refresh()
    } catch (e) {
      notify(e.message, 'err')
    }
  }

  const onNotify = async () => {
    try {
      const r = await api.notify(alertId, filters.source)
      const ok = r.results.filter((x) => x.ok).map((x) => x.channel)
      notify(ok.length ? `${t('d.sent')}: ${ok.join(', ')}` : r.results.map((x) => `${x.channel}: ${x.error}`).join(' · '), ok.length ? 'ok' : 'err')
    } catch (e) {
      notify(e.message, 'err')
    }
  }

  const setHours = (h) => setFilters((f) => ({ ...f, hours: h }))
  const mapProps = {
    offline: health ? !!health.offline : null, lastIngest: health?.last_ingest?.finished_at,
    source: filters.source, hours: filters.hours, refreshKey: tick,
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header page={route.page} onHome={() => go('/')} onBack={back} health={health} busy={busy} onIngest={onIngest}
        title={route.page === 'alert' ? (detail?.zone_label || '') : ''} />
      {error && <div className="mx-4 mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300 ring-1 ring-red-500/30">{t('t.backend', { e: error })}</div>}

      <main className="mx-auto w-full max-w-6xl flex-1 p-3 sm:p-4">
        {route.page === 'home' && <Home alerts={data.alerts} stats={stats} onGo={go} onOpenAlert={openAlert} />}

        {route.page === 'alerts' && (
          <div className="mx-auto max-w-3xl space-y-3">
            <Filters filters={filters} setFilters={setFilters} zones={data.zones} />
            <AlertList alerts={data.alerts} total={data.total} onSelect={openAlert} />
          </div>
        )}

        {route.page === 'map' && (
          <div className="space-y-2">
            <p className="text-sm text-slate-400">{t('page.mapHint')}</p>
            <ThreatMap alerts={data.alerts} onSelect={openAlert} tall {...mapProps} />
          </div>
        )}

        {route.page === 'alert' && (
          <div className="mx-auto max-w-4xl">
            {detailState === 'missing' ? (
              <div className="panel p-10 text-center text-slate-400">
                {t('page.alertGone')}
                <div className="mt-4"><button onClick={() => go('/alerts')} className="rounded-lg bg-slate-800 px-4 py-2 text-sm text-slate-200">{t('page.toAlerts')}</button></div>
              </div>
            ) : (
              <AlertDetail
                key={detail?.id}
                alert={detail?.id === alertId ? detail : null}
                loading
                source={filters.source}
                notifyEnabled={(health?.notify_channels || []).length > 0}
                onFeedback={onFeedback}
                onNotify={onNotify}
                onReclassify={onReclassify}
                publicMode={!!health?.public_mode}
                aiEnabled={!!health?.llm_enabled && !health?.offline}
                mapProps={mapProps}
              />
            )}
          </div>
        )}

        {route.page === 'stats' && <StatsPanel source={filters.source} hours={filters.hours} refreshKey={tick} setHours={setHours} />}
        {route.page === 'news' && <SignalStream source={filters.source} hours={filters.hours} alertsCount={data.total} refreshKey={tick} />}
        {route.page === 'analyze' && <AnalyzePanel />}
        {route.page === 'network' && <NetworkGraph source={filters.source} refreshKey={tick} onOpenAlert={openAlert} />}
        {route.page === 'help' && <HelpPage />}
      </main>

      {toast && (
        <div className={`fixed bottom-4 left-3 right-3 z-[3000] max-w-md rounded-lg px-4 py-3 text-sm shadow-xl ring-1 sm:left-auto sm:right-4 ${toast.kind === 'err' ? 'bg-red-950 text-red-200 ring-red-500/40' : toast.kind === 'warn' ? 'bg-amber-950 text-amber-100 ring-amber-500/40' : 'bg-slate-900 text-slate-100 ring-slate-600'}`}>
          {toast.msg}
        </div>
      )}
    </div>
  )
}
