import { useCallback, useEffect, useState } from 'react'
import AlertDetail from './components/AlertDetail'
import AlertList from './components/AlertList'
import AnalyzePanel from './components/AnalyzePanel'
import Filters from './components/Filters'
import Header from './components/Header'
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
  const { t } = useI18n()
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
      const [a, s, h] = await Promise.all([api.alerts(filters), api.stats(filters.source), api.health()])
      setData(a)
      setStats(s)
      setHealth(h)
      setError(null)
      setSelectedId((prev) => (a.alerts.some((x) => x.id === prev) ? prev : a.alerts[0]?.id ?? null))
      setTick((x) => x + 1)
    } catch (e) {
      setError(e.message)
    }
  }, [filters])

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
    api.alert(selectedId, filters.source)
      .then((d) => alive && setDetail(d))
      .catch(() => alive && setDetail(null))
      .finally(() => alive && setDetailLoading(false))
    return () => { alive = false }
  }, [selectedId, filters.source, tick])

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
      const failed = r.sources.filter((s) => !s.ok).map((s) => s.source)
      notify(t('t.ingest', { f: r.fetched, i: r.inserted, r: r.threat_relevant }) + (failed.length ? ` · ${t('t.failed')}: ${failed.join(', ')}` : ''), failed.length ? 'warn' : 'ok')
      await refresh()
    } catch (e) {
      notify(e.message, 'err')
    } finally {
      setBusy(null)
    }
  }

  const onReset = async () => {
    setBusy('reset')
    try {
      const r = await api.reset()
      notify(t('t.reset', { n: r.loaded }))
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

  return (
    <div className="flex min-h-screen flex-col">
      <Header view={view} setView={setView} health={health} busy={busy} onIngest={onIngest} onReset={onReset} />
      {error && <div className="mx-4 mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300 ring-1 ring-red-500/30">{t('t.backend', { e: error })}</div>}
      <KpiBar stats={stats} />

      {view === 'board' && (
        <main className="grid flex-1 grid-cols-12 gap-4 p-4">
          <section className="col-span-12 flex flex-col gap-3 lg:sticky lg:top-[76px] lg:col-span-4 lg:h-[calc(100vh-92px)] xl:col-span-3">
            <Filters filters={filters} setFilters={setFilters} zones={data.zones} />
            <AlertList alerts={data.alerts} total={data.total} selectedId={selectedId} onSelect={setSelectedId} />
          </section>
          <section className="col-span-12 flex min-w-0 flex-col gap-4 lg:col-span-8 xl:col-span-9">
            <ThreatMap alerts={data.alerts} selectedId={selectedId} detail={detail} onSelect={setSelectedId} />
            <AlertDetail
              key={detail?.id}
              alert={detail}
              loading={detailLoading || (!!selectedId && !detail)}
              source={filters.source}
              notifyEnabled={(health?.notify_channels || []).length > 0}
              onFeedback={onFeedback}
              onClearFeedback={onClearFeedback}
              onNotify={onNotify}
            />
          </section>
        </main>
      )}
      {view === 'network' && <NetworkGraph source={filters.source} refreshKey={tick} onOpenAlert={openAlert} />}
      {view === 'signals' && <SignalStream source={filters.source} alertsCount={data.total} refreshKey={tick} />}
      {view === 'analyze' && <AnalyzePanel />}

      {toast && (
        <div className={`fixed bottom-4 right-4 z-[3000] max-w-md rounded-lg px-4 py-3 text-sm shadow-xl ring-1 ${toast.kind === 'err' ? 'bg-red-950 text-red-200 ring-red-500/40' : toast.kind === 'warn' ? 'bg-amber-950 text-amber-100 ring-amber-500/40' : 'bg-slate-900 text-slate-100 ring-slate-600'}`}>
          {toast.msg}
        </div>
      )}
    </div>
  )
}
