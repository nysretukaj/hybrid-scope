import { useEffect, useRef, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { cat, level } from '../lib/format'
import { useI18n } from '../lib/i18n'

const TILE_ERRORS_BEFORE_FALLBACK = 4
const VECTOR_STYLE = { color: '#334155', weight: 0.8, fillColor: '#111a2e', fillOpacity: 1 }

function FlyTo({ target, id }) {
  const map = useMap()
  useEffect(() => {
    if (target) map.flyTo([target.lat, target.lon], Math.max(map.getZoom(), 6), { duration: 0.9 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])
  return null
}

/** Country outlines bundled with the app (Natural Earth via world-atlas), loaded only when needed. */
function useVectorBasemap(enabled) {
  const [geo, setGeo] = useState(null)
  useEffect(() => {
    if (!enabled || geo) return
    let alive = true
    Promise.all([import('world-atlas/countries-50m.json'), import('topojson-client')]).then(([topo, tc]) => {
      const t = topo.default || topo
      if (alive) setGeo(tc.feature(t, t.objects.countries))
    })
    return () => { alive = false }
  }, [enabled, geo])
  return geo
}

export default function ThreatMap({ alerts, selectedId, detail, onSelect, offline }) {
  const { t } = useI18n()
  const [tilesFailed, setTilesFailed] = useState(false)
  const tileErrors = useRef(0)
  // offline is null until the backend has answered: draw no basemap yet, so an offline demo
  // never even tries to reach the tile server
  const useVector = offline === true || tilesFailed
  const showTiles = offline === false && !tilesFailed
  const geo = useVectorBasemap(useVector)
  const located = detail?.signals?.filter((s) => s.lat != null) || []

  const onTileError = () => {
    tileErrors.current += 1
    if (tileErrors.current >= TILE_ERRORS_BEFORE_FALLBACK) setTilesFailed(true)
  }

  return (
    <div className="panel relative overflow-hidden">
      <MapContainer center={[50, 15]} zoom={4} minZoom={2} maxZoom={useVector ? 8 : 16} worldCopyJump className="h-[340px] w-full" zoomControl={false}>
        {useVector && geo && <GeoJSON key="vector-basemap" data={geo} style={VECTOR_STYLE} interactive={false} />}
        {showTiles && (
          <>
            <TileLayer
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
              attribution="Tiles &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors"
              maxZoom={16}
              eventHandlers={{ tileerror: onTileError }}
            />
            <TileLayer
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
              maxZoom={16}
              opacity={0.6}
            />
          </>
        )}
        {alerts.filter((a) => a.centroid).map((a) => {
          const l = level(a.level)
          const selected = a.id === selectedId
          return (
            <CircleMarker
              key={a.id}
              center={[a.centroid.lat, a.centroid.lon]}
              radius={6 + a.score / 7}
              pathOptions={{ color: l.color, fillColor: l.color, fillOpacity: selected ? 0.35 : 0.18, weight: selected ? 2.5 : 1.2, dashArray: a.is_hybrid ? null : '3 4' }}
              eventHandlers={{ click: () => onSelect(a.id) }}
            >
              <Tooltip direction="top">
                <b>{a.zone}</b> · {a.level} {Math.round(a.score)}{a.is_hybrid ? ' · hybrid' : ''}
              </Tooltip>
            </CircleMarker>
          )
        })}
        {detail && detail.centroid && located.map((s) => (
          <Polyline key={`l-${s.id}`} positions={[[detail.centroid.lat, detail.centroid.lon], [s.lat, s.lon]]} pathOptions={{ color: cat(s.category).color, weight: 1, opacity: 0.35 }} />
        ))}
        {located.map((s) => (
          <CircleMarker
            key={s.id}
            center={[s.lat, s.lon]}
            radius={4}
            pathOptions={{ color: '#0b1220', weight: 1, fillColor: cat(s.category).color, fillOpacity: 0.95 }}
          >
            <Tooltip direction="top">{s.title}</Tooltip>
          </CircleMarker>
        ))}
        <FlyTo target={detail?.centroid} id={detail?.id} />
      </MapContainer>
      <div className="pointer-events-none absolute bottom-2 left-2 z-[500] flex gap-3 rounded-md bg-slate-950/80 px-2 py-1 text-[10px] text-slate-400 ring-1 ring-slate-800">
        <span>{t('m.hybrid')}</span>
        <span>{t('m.single')}</span>
        <span>{t('m.size')}</span>
        {useVector && <span className="text-amber-300/80">{t('m.offlineMap')}</span>}
      </div>
    </div>
  )
}
