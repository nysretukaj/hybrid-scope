import { useCallback, useEffect, useState } from 'react'
import AlertDetail from './components/AlertDetail'
import AlertList from './components/AlertList'
import AnalyzePanel from './components/AnalyzePanel'
import Filters from './components/Filters'
import Header from './components/Header'
import KpiBar from './components/KpiBar'
import SignalStream from './components/SignalStream'
import ThreatMap from './components/ThreatMap'
import { api } from './lib/api'

const POLL_MS = 30000

export default function App() {
  const [view, setView] = useState('alerts')
  const [filters, setFilters] = useState({ q: '', category: '', zone: '', source: 'all', min_confidence: 0, hybrid_only: false })
  const [data, setData] = useState({ alerts: [], zones: [], total: 0 })
  const [stats, setStats] = useState(null)
  const [health, setHealth] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
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
      setTick((t) => t + 1)
    } catch (e) {
      setError(`Backend unreachable (${e.message}). Is the API running on :8000?`)
    }
  }, [filters])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, POLL_MS)
    return () => clearInterval(id)
  }, [refresh])

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

  const notify = (msg, kind = 'ok') => {
    setToast({ msg, kind })
    setTimeout(() => setToast(null), 6000)
  }

  const onIngest = async () => {
    setBusy('ingest')
    try {
      const r = await api.ingest()
      const failed = r.sources.filter((s) => !s.ok).map((s) => s.source)
      notify(`Live ingest: ${r.fetched} items fetched, ${r.inserted} new, ${r.threat_relevant} threat-relevant${failed.length ? ` · failed: ${failed.join(', ')}` : ''}`, failed.length ? 'warn' : 'ok')
      await refresh()
    } catch (e) {
      notify(`Live ingest failed: ${e.message}`, 'err')
    } finally {
      setBusy(null)
    }
  }

  const onReset = async () => {
    setBusy('reset')
    try {
      const r = await api.reset()
      notify(`Scenario re-anchored to now (${r.loaded} signals)`)
      await refresh()
    } catch (e) {
      notify(`Reset failed: ${e.message}`, 'err')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header view={view} setView={setView} health={health} busy={busy} onIngest={onIngest} onReset={onReset} />
      {error && <div className="mx-4 mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300 ring-1 ring-red-500/30">{error}</div>}
      <KpiBar stats={stats} />

      {view === 'alerts' && (
        <main className="grid flex-1 grid-cols-12 gap-4 p-4">
          <section className="col-span-12 flex flex-col gap-3 lg:sticky lg:top-[76px] lg:col-span-4 lg:h-[calc(100vh-92px)] xl:col-span-3">
            <Filters filters={filters} setFilters={setFilters} zones={data.zones} />
            <AlertList alerts={data.alerts} total={data.total} selectedId={selectedId} onSelect={setSelectedId} />
          </section>
          <section className="col-span-12 flex min-w-0 flex-col gap-4 lg:col-span-8 xl:col-span-9">
            <ThreatMap alerts={data.alerts} selectedId={selectedId} detail={detail} onSelect={setSelectedId} />
            <AlertDetail key={detail?.id} alert={detail} loading={detailLoading || (!!selectedId && !detail)} />
          </section>
        </main>
      )}
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
