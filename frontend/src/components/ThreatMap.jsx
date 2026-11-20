import L from 'leaflet'
import { useEffect, useMemo, useRef, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap, ZoomControl } from 'react-leaflet'
import { api } from '../lib/api'
import { cat, level, levelLabel, timeAgo } from '../lib/format'
import { useI18n } from '../lib/i18n'

const TILE_ERRORS_BEFORE_FALLBACK = 4
const LEVEL_RANK = { LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3 }
const CAT_ICON = { disinformation: '📢', political: '🏛️', cyber: '💻', infrastructure: '⚡', physical: '🚨' }

// Esri basemaps: no API key, attribution shown in the map corner.
const BASEMAPS = {
  satellite: [
    { url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics' },
    { url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', opacity: 0.9 },
  ],
  streets: [
    { url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', attribution: '&copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors' },
  ],
  dark: [
    { url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', attribution: 'Tiles &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors' },
    { url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', opacity: 0.6 },
  ],
}
// Country names in our data -> names in the bundled Natural Earth outlines
const WORLD_NAME = { 'United States': 'United States of America', 'North Macedonia': 'Macedonia', 'Bosnia and Herzegovina': 'Bosnia and Herz.' }

function readBasemap() {
  try { return BASEMAPS[localStorage.getItem('hs-basemap')] ? localStorage.getItem('hs-basemap') : 'satellite' } catch { return 'satellite' }
}

function FlyTo({ target, id }) {
  const map = useMap()
  useEffect(() => {
    if (target) map.flyTo([target.lat, target.lon], Math.max(map.getZoom(), 6), { duration: 0.9 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])
  return null
}

function ResizeOn({ value }) {
  const map = useMap()
  useEffect(() => { const id = setTimeout(() => map.invalidateSize(), 220); return () => clearTimeout(id) }, [value, map])
  return null
}

/**
 * Keep the page easy to scroll: in the embedded map the mouse wheel scrolls the page (use +/− or
 * fullscreen to zoom) and on touch screens one finger scrolls the page while two fingers move the map.
 */
function Interactions({ fullscreen }) {
  const map = useMap()
  useEffect(() => {
    if (fullscreen) map.scrollWheelZoom.enable()
    else map.scrollWheelZoom.disable()
    if (L.Browser.mobile) {
      if (fullscreen) map.dragging.enable()
      else map.dragging.disable()
    }
  }, [fullscreen, map])
  return null
}

/** Country outlines bundled with the app (Natural Earth via world-atlas): risk shading online, the whole basemap offline. */
function useCountries() {
  const [geo, setGeo] = useState(null)
  useEffect(() => {
    let alive = true
    Promise.all([import('world-atlas/countries-50m.json'), import('topojson-client')]).then(([topo, tc]) => {
      const t = topo.default || topo
      if (alive) setGeo(tc.feature(t, t.objects.countries))
    })
    return () => { alive = false }
  }, [])
  return geo
}

function alertIcon(a, selected, label) {
  const color = level(a.level).color
  const size = Math.round(14 + a.score / 6)
  const rings = a.level === 'CRITICAL' || a.level === 'HIGH'
    ? `<span class="ring"></span><span class="ring r2"></span>` : ''
  // a dashed outline = only the country is known, so the point is approximate
  const approx = a.geo_precision === 'country' ? ' approx' : ''
  const html = `<div class="hs-marker ${a.level.toLowerCase()}${selected ? ' selected' : ''}${approx}" style="--c:${color};width:${size}px;height:${size}px">
    ${rings}<span class="core">${a.is_hybrid ? '◆' : ''}</span>
    ${label ? `<span class="hs-label">${label}</span>` : ''}</div>`
  return L.divIcon({ html, className: 'hs-icon', iconSize: [size, size], iconAnchor: [size / 2, size / 2] })
}

/** Reports at the same place are drawn as one marker with a count, instead of a pile of overlapping ones. */
function signalGroupIcon(group) {
  const s = group[0]
  const color = cat(s.category).color
  const approx = s.geo_precision === 'country' ? ' approx' : ''
  const badge = group.length > 1 ? `<span class="hs-count">${group.length}</span>` : ''
  return L.divIcon({
    html: `<div class="hs-sig${approx}" style="background:${color}">${CAT_ICON[s.category] || '•'}${badge}</div>`,
    className: 'hs-icon', iconSize: [24, 24], iconAnchor: [12, 12],
  })
}

function groupByPlace(items, getPos) {
  const groups = new Map()
  for (const it of items) {
    const [lat, lon] = getPos(it)
    const key = `${lat.toFixed(2)},${lon.toFixed(2)}`
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(it)
  }
  return [...groups.values()]
}

/** Alerts that share a point (e.g. two alerts for one country) are spread in a small circle so each can be clicked. */
function spreadAlerts(alerts) {
  const out = []
  for (const group of groupByPlace(alerts, (a) => [a.centroid.lat, a.centroid.lon])) {
    group.forEach((a, i) => {
      if (i === 0) { out.push({ a, pos: [a.centroid.lat, a.centroid.lon] }); return }
      const angle = (2 * Math.PI * i) / group.length
      out.push({ a, pos: [a.centroid.lat + 0.6 * Math.sin(angle), a.centroid.lon + 0.9 * Math.cos(angle)] })
    })
  }
  return out
}

/** Density layer: one soft circle per place, bigger where more threat reports come from. */
function DensityLayer({ points }) {
  return points.map((p) => (
    <CircleMarker key={`${p.lat},${p.lon}`} center={[p.lat, p.lon]} radius={8 + 6 * Math.sqrt(p.count)}
      pathOptions={{ stroke: false, fillColor: level(p.max_severity >= 0.75 ? 'CRITICAL' : p.max_severity >= 0.55 ? 'HIGH' : 'MEDIUM').color, fillOpacity: 0.28 }}>
      <Tooltip direction="top">{p.label || ''} · {p.count}</Tooltip>
    </CircleMarker>
  ))
}

export default function ThreatMap({ alerts, selectedId, detail, onSelect, offline, lastIngest, source, hours, refreshKey, tall, compact }) {
  const { t, lang } = useI18n()
  const [density, setDensity] = useState(false)
  const [points, setPoints] = useState([])
  useEffect(() => {
    if (!density) return undefined
    let alive = true
    api.geo(source, hours, lang).then((d) => alive && setPoints(d.points)).catch(() => alive && setPoints([]))
    return () => { alive = false }
  }, [density, source, hours, lang, refreshKey])
  // the badge says what is really shown: live news, only the exercise scenario, or the offline snapshot
  const status = offline ? 'offline' : alerts.some((a) => !a.synthetic) ? 'live' : 'scenario'
  const [basemap, setBasemap] = useState(readBasemap)
  const [tilesFailed, setTilesFailed] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const [, setClock] = useState(0)
  const tileErrors = useRef(0)
  const countries = useCountries()

  // offline is null until the backend has answered: no basemap request before we know
  const useVector = offline === true || tilesFailed
  const showTiles = offline === false && !tilesFailed
  const located = detail?.signals?.filter((s) => s.lat != null) || []
  const signalGroups = groupByPlace(located, (s) => [s.lat, s.lon])

  useEffect(() => { const id = setInterval(() => setClock((c) => c + 1), 15000); return () => clearInterval(id) }, [])
  useEffect(() => {
    if (!fullscreen) return
    const onKey = (e) => e.key === 'Escape' && setFullscreen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [fullscreen])

  const chooseBasemap = (b) => {
    setBasemap(b)
    try { localStorage.setItem('hs-basemap', b) } catch { /* storage unavailable */ }
  }

  // highest alert level per country, for the shading
  const countryRisk = useMemo(() => {
    const m = {}
    for (const a of alerts) {
      for (const c of a.countries || []) {
        const name = WORLD_NAME[c] || c
        if (!m[name] || LEVEL_RANK[a.level] > LEVEL_RANK[m[name].level]) m[name] = { level: a.level, label: a.zone_label || a.zone }
      }
    }
    return m
  }, [alerts])
  const riskKey = Object.entries(countryRisk).map(([k, v]) => `${k}:${v.level}`).sort().join('|') + `|${basemap}|${useVector}|${t('map.legend')}`

  const countryStyle = (f) => {
    const r = countryRisk[f.properties.name]
    const base = useVector ? { color: '#334155', weight: 0.8, fillColor: '#111a2e', fillOpacity: 1 } : { color: 'transparent', weight: 0, fillOpacity: 0 }
    if (!r) return base
    const c = level(r.level).color
    return { ...base, color: c, weight: 1.6, fillColor: c, fillOpacity: useVector ? 0.45 : (basemap === 'satellite' ? 0.28 : 0.22) }
  }
  const onEachCountry = (f, layer) => {
    const r = countryRisk[f.properties.name]
    if (r) layer.bindTooltip(`<b>${r.label}</b><br/>${t('map.country', { level: levelLabel(r.level) })}`, { sticky: true })
  }

  const onTileError = () => {
    tileErrors.current += 1
    if (tileErrors.current >= TILE_ERRORS_BEFORE_FALLBACK) setTilesFailed(true)
  }

  // permanent name labels only for the most important alerts, to keep the map readable
  const labelled = new Set(alerts.filter((a) => a.centroid && (a.level === 'CRITICAL' || a.id === selectedId)).map((a) => a.id))

  return (
    <div className={`panel relative overflow-hidden ${fullscreen ? 'map-fullscreen' : ''}`}>
      <MapContainer center={[48, 18]} zoom={4} minZoom={2} maxZoom={useVector ? 8 : 17} worldCopyJump zoomControl={false}
        className={`w-full ${fullscreen ? 'h-full' : tall ? 'h-[calc(100vh-150px)] min-h-[380px]' : compact ? 'h-[260px] sm:h-[320px]' : 'h-[300px] sm:h-[380px] xl:h-[460px]'}`}>
        <ResizeOn value={fullscreen} />
        <Interactions fullscreen={fullscreen} />
        <ZoomControl position="bottomright" />
        {showTiles && BASEMAPS[basemap].map((layer, k) => (
          <TileLayer key={`${basemap}-${k}`} url={layer.url} attribution={layer.attribution} opacity={layer.opacity ?? 1}
            maxZoom={17} eventHandlers={k === 0 ? { tileerror: onTileError } : undefined} />
        ))}
        {countries && <GeoJSON key={riskKey} data={countries} style={countryStyle} onEachFeature={onEachCountry} />}

        {density && <DensityLayer points={points} />}

        {detail?.centroid && signalGroups.map((g) => (
          <Polyline key={`l-${g[0].id}`} positions={[[detail.centroid.lat, detail.centroid.lon], [g[0].lat, g[0].lon]]}
            pathOptions={{ color: cat(g[0].category).color, weight: 2, opacity: 0.85, className: 'hs-flow' }} />
        ))}
        {signalGroups.map((g) => (
          <Marker key={g[0].id} position={[g[0].lat, g[0].lon]} icon={signalGroupIcon(g)}>
            <Tooltip direction="top" offset={[0, -10]}>
              {g[0].geo_precision === 'country' && <div className="text-[10px] italic">{t('map.approx')}</div>}
              {g.slice(0, 4).map((s) => <div key={s.id}>{CAT_ICON[s.category]} {s.title}</div>)}
              {g.length > 4 && <div>+{g.length - 4}</div>}
            </Tooltip>
          </Marker>
        ))}
        {spreadAlerts(alerts.filter((a) => a.centroid)).map(({ a, pos }) => (
          <Marker
            key={a.id}
            position={pos}
            icon={alertIcon(a, a.id === selectedId, labelled.has(a.id) ? `${a.zone_label || a.zone} · ${Math.round(a.score)}` : '')}
            zIndexOffset={a.id === selectedId ? 1000 : LEVEL_RANK[a.level] * 100}
            eventHandlers={{ click: () => onSelect(a.id) }}
          >
            {!labelled.has(a.id) && (
              <Tooltip direction="top" offset={[0, -8]}>
                <b>{a.zone_label || a.zone}</b> · {levelLabel(a.level)} {Math.round(a.score)}
                {a.geo_precision === 'country' && <div className="text-[10px] italic">{t('map.approx')}</div>}
              </Tooltip>
            )}
          </Marker>
        ))}
        <FlyTo target={detail?.centroid} id={detail?.id} />
      </MapContainer>

      {/* data status: live news, exercise scenario only, or offline snapshot */}
      <div className="pointer-events-none absolute left-2 top-2 z-[500] flex items-center gap-2 rounded-md bg-slate-950/85 px-2 py-1 text-[11px] text-slate-300 ring-1 ring-slate-700"
        title={t(`map.status.${status}Tip`)}>
        <span className={`relative inline-block h-2 w-2 rounded-full ${status === 'live' ? 'text-red-500 live-dot' : 'text-amber-400'}`} style={{ background: 'currentColor' }} />
        <span className={`font-semibold tracking-widest ${status === 'live' ? 'text-red-300' : 'text-amber-300'}`}>{t(`map.status.${status}`)}</span>
        <span className="hidden text-slate-400 sm:inline">
          · {lastIngest ? t('map.lastIngest', { t: timeAgo(lastIngest) }) : t('map.noIngest')}
        </span>
      </div>

      {/* basemap switcher + full screen */}
      <div className="absolute right-2 top-2 z-[500] flex gap-1">
        {!useVector && (
          <div className="flex rounded-md bg-slate-950/85 p-0.5 ring-1 ring-slate-700">
            {Object.keys(BASEMAPS).map((b) => (
              <button key={b} onClick={() => chooseBasemap(b)}
                className={`rounded px-2 py-1 text-[11px] ${basemap === b ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-200'}`}>
                {t(`map.${b}`)}
              </button>
            ))}
          </div>
        )}
        <button onClick={() => setDensity((d) => !d)} aria-pressed={density} title={t('map.densityTip')}
          className={`rounded-md px-2 py-1 text-[11px] ring-1 ${density ? 'bg-orange-500/25 text-orange-100 ring-orange-400/50' : 'bg-slate-950/85 text-slate-300 ring-slate-700 hover:bg-slate-800'}`}>
          🔥<span className="hidden sm:inline"> {t('map.density')}</span>
        </button>
        <button onClick={() => setFullscreen((f) => !f)} title={fullscreen ? t('map.exit') : t('map.fullscreen')}
          aria-label={fullscreen ? t('map.exit') : t('map.fullscreen')}
          className="rounded-md bg-slate-950/85 px-2 py-1 text-sm text-slate-200 ring-1 ring-slate-700 hover:bg-slate-800">
          {fullscreen ? '✕' : '⛶'}
        </button>
      </div>

      {/* legend: colours plus what they mean */}
      <div className="pointer-events-none absolute bottom-2 left-2 z-[500] rounded-md bg-slate-950/85 px-2.5 py-1.5 text-[10px] text-slate-300 ring-1 ring-slate-700">
        <div className="mb-1 font-semibold uppercase tracking-widest text-slate-500">{t('map.legend')}</div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 sm:grid-cols-1">
          {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((l) => (
            <span key={l} className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: level(l).color }} />
              {levelLabel(l)}<span className="hidden text-slate-500 sm:inline">· {t(`lv.${l}`)}</span>
            </span>
          ))}
        </div>
        <div className="mt-1 hidden items-center gap-1.5 text-slate-400 sm:flex">
          <span className="h-2.5 w-2.5 rounded-full border border-dashed border-slate-300" />{t('map.approxLegend')}
        </div>
        {useVector && <div className="mt-1 text-amber-300/80">{t('m.offlineMap')}</div>}
      </div>
    </div>
  )
}
