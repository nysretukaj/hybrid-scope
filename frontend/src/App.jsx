import { useCallback, useEffect, useState } from 'react'
import AlertDetail from './components/AlertDetail'
import AlertList from './components/AlertList'
import AnalyzePanel from './components/AnalyzePanel'
import Filters from './components/Filters'
import Header, { BottomNav } from './components/Header'
import { Onboarding, StatusBanner } from './components/StatusBanner'
import KpiBar from './components/KpiBar'
import NetworkGraph from './components/NetworkGraph'
import SignalStream from './components/SignalStream'
import ThreatMap from './components/ThreatMap'
import { api } from './lib/api'
import { useI18n } from './lib/i18n'

const POLL_MS = 30000

function hashAlert() {
  const m = window.location.hash.match(/alert=([\w-]+)/)
  return m ? m[1] : null
}

export default function App() {
  const { t, lang } = useI18n()
  const [view, setView] = useState('board')
  const [filters, setFilters] = useState({ q: '', category: '', zone: '', source: 'all', min_confidence: 0, hybrid_only: false, hide_dismissed: false })
  const [data, setData] = useState({ alerts: [], zones: [], total: 0 })
  const [stats, setStats] = useState(null)
  const [health, setHealth] = useState(null)
  const [selectedId, setSelectedId] = useState(hashAlert)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [tick, setTick] = useState(0)
  const [busy, setBusy] = useState(null)
  const [toast, setToast] = useState(null)
  const [error, setError] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const [a, s, h] = await Promise.all([api.alerts(filters, lang), api.stats(filters.source), api.health()])
      setData(a)
      setStats(s)
      setHealth(h)
      setError(null)
      setSelectedId((prev) => (a.alerts.some((x) => x.id === prev) ? prev : a.alerts[0]?.id ?? null))
      setTick((x) => x + 1)
    } catch (e) {
      setError(e.message)
    }
  }, [filters, lang])

  const enriching = !!health?.llm?.enrich?.running
  useEffect(() => {
    refresh()
    // poll faster while the LLM is upgrading live signals, so the board visibly updates
    const id = setInterval(refresh, enriching ? 6000 : POLL_MS)
    return () => clearInterval(id)
  }, [refresh, enriching])

  useEffect(() => {
    if (!selectedId) { setDetail(null); return }
    let alive = true
    setDetailLoading(true)
    api.alert(selectedId, filters.source, lang)
      .then((d) => alive && setDetail(d))
      .catch(() => alive && setDetail(null))
      .finally(() => alive && setDetailLoading(false))
    return () => { alive = false }
  }, [selectedId, filters.source, tick, lang])

  useEffect(() => {
    if (selectedId) window.history.replaceState(null, '', `#alert=${selectedId}`)
  }, [selectedId])

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
      const r = await api.feedback(selectedId, filters.source, verdict, note)
      notify(t('t.feedback', { n: r.sources_updated.length }))
      await refresh()
    } catch (e) {
      notify(e.message, 'err')
    }
  }

  const onClearFeedback = async () => {
    await api.clearFeedback(selectedId)
    await refresh()
  }

  const onNotify = async () => {
    try {
      const r = await api.notify(selectedId, filters.source)
      const ok = r.results.filter((x) => x.ok).map((x) => x.channel)
      notify(ok.length ? `${t('d.sent')}: ${ok.join(', ')}` : r.results.map((x) => `${x.channel}: ${x.error}`).join(' · '), ok.length ? 'ok' : 'err')
    } catch (e) {
      notify(e.message, 'err')
    }
  }

  const openAlert = (id) => {
    setSelectedId(id)
    setView('board')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // On phones the details sit below the list, so bring them into view when an alert is chosen.
  const selectAlert = (id) => {
    setSelectedId(id)
    if (window.innerWidth < 1024) {
      setTimeout(() => document.getElementById('alert-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 150)
    }
  }

  const openFromBanner = (id) => {
    setSelectedId(id)
    setTimeout(() => document.getElementById('alert-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 150)
  }

  return (
    <div className="has-bottom-nav flex min-h-screen flex-col">
      <Header view={view} setView={setView} health={health} busy={busy} onIngest={onIngest} />
      {error && <div className="mx-4 mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300 ring-1 ring-red-500/30">{t('t.backend', { e: error })}</div>}
      <KpiBar stats={stats} />

      {view === 'board' && (
        <div className="space-y-3 px-3 pt-3 sm:px-4">
          <StatusBanner alerts={data.alerts} onOpen={openFromBanner} />
          <Onboarding />
        </div>
      )}

      {view === 'board' && (
        // Phone order: map → list → details. Desktop: list on the left, map above details on the right.
        <main className="grid flex-1 grid-cols-1 items-start gap-4 p-3 sm:p-4 lg:grid-cols-12">
          <section className="min-w-0 lg:col-span-8 lg:col-start-5 lg:row-start-1 xl:col-span-9 xl:col-start-4">
            <ThreatMap alerts={data.alerts} selectedId={selectedId} detail={detail} onSelect={selectAlert}
              offline={health ? !!health.offline : null} updatedAt={data.generated_at} />
          </section>
          <section className="flex min-w-0 flex-col gap-3 lg:sticky lg:top-[76px] lg:col-span-4 lg:col-start-1 lg:row-span-2 lg:row-start-1 lg:h-[calc(100vh-92px)] xl:col-span-3">
            <Filters filters={filters} setFilters={setFilters} zones={data.zones} />
            <AlertList alerts={data.alerts} total={data.total} selectedId={selectedId} onSelect={selectAlert} />
          </section>
          <section id="alert-detail" className="min-w-0 scroll-mt-3 lg:col-span-8 lg:col-start-5 lg:row-start-2 lg:scroll-mt-24 xl:col-span-9 xl:col-start-4">
            <AlertDetail
              key={detail?.id}
              alert={detail}
              loading={detailLoading || (!!selectedId && !detail)}
              source={filters.source}
              notifyEnabled={(health?.notify_channels || []).length > 0}
              onFeedback={onFeedback}
              onClearFeedback={onClearFeedback}
              onNotify={onNotify}
              publicMode={!!health?.public_mode}
            />
          </section>
        </main>
      )}
      {view === 'network' && <NetworkGraph source={filters.source} refreshKey={tick} onOpenAlert={openAlert} />}
      {view === 'signals' && <SignalStream source={filters.source} alertsCount={data.total} refreshKey={tick} />}
      {view === 'analyze' && <AnalyzePanel />}

      <BottomNav view={view} setView={setView} />

      {toast && (
        <div className={`fixed bottom-20 left-3 right-3 z-[3000] sm:left-auto sm:right-4 lg:bottom-4 max-w-md rounded-lg px-4 py-3 text-sm shadow-xl ring-1 ${toast.kind === 'err' ? 'bg-red-950 text-red-200 ring-red-500/40' : toast.kind === 'warn' ? 'bg-amber-950 text-amber-100 ring-amber-500/40' : 'bg-slate-900 text-slate-100 ring-slate-600'}`}>
          {toast.msg}
        </div>
      )}
    </div>
  )
}
