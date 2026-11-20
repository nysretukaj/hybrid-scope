import { useState } from 'react'
import { VERIFICATION, cat, level, timeAgo } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { HybridBadge, LevelBadge, LiveBadge } from './ui'

const MOBILE_LIMIT = 5

export default function AlertList({ alerts, selectedId, onSelect, total }) {
  const { t } = useI18n()
  const [showAll, setShowAll] = useState(false)
  const hiddenOnMobile = alerts.length - MOBILE_LIMIT
  return (
    <div className="panel flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2.5">
        <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{t('list.title')}</span>
        <span className="font-mono text-[11px] text-slate-500">{alerts.length}/{total}</span>
      </div>
      <div className="scroll-thin min-h-0 flex-1 space-y-1.5 overflow-y-auto p-2">
        {alerts.length === 0 && <div className="p-6 text-center text-sm text-slate-500">{t('list.none')}</div>}
        {alerts.map((a, i) => {
          const l = level(a.level)
          const mobileHidden = !showAll && i >= MOBILE_LIMIT
          const selected = a.id === selectedId
          const verdict = a.verification || 'unverified'
          const vstyle = VERIFICATION[verdict]
          return (
            <button
              key={a.id}
              onClick={() => onSelect(a.id)}
              className={`${mobileHidden ? 'hidden lg:block' : ''} group relative w-full overflow-hidden rounded-lg py-2.5 pl-4 pr-3 text-left ring-1 transition ${selected ? 'bg-slate-800/80 ring-slate-500' : 'bg-slate-900/40 ring-slate-800 hover:bg-slate-800/50 hover:ring-slate-700'} ${verdict === 'disproved' ? 'opacity-50' : ''}`}
            >
              <span className="absolute inset-y-0 left-0 w-1" style={{ background: l.color, boxShadow: selected ? `0 0 12px ${l.color}` : 'none' }} />
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <LevelBadge value={a.level} />
                    {a.is_hybrid && <HybridBadge />}
                    {!a.synthetic && <LiveBadge />}
                    {verdict !== 'unverified' && (
                      <span className="rounded-full px-1.5 text-[10px] ring-1" style={{ color: vstyle.color, '--tw-ring-color': `${vstyle.color}66` }}>
                        {vstyle.icon} {t(`v.${verdict}`)}
                      </span>
                    )}
                  </div>
                  <div className="mt-1.5 truncate text-sm font-medium text-slate-100">{a.zone_label || a.zone}</div>
                  <div className="truncate text-xs text-slate-400" title={a.headline}>{a.headline}</div>
                  <div className="mt-1 text-[11px] font-medium" style={{ color: l.color }}>→ {t(`lv.${a.level}`)}</div>
                  <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
                    <span className="flex gap-1">
                      {a.categories.map((c) => (
                        <span key={c} className="h-2 w-2 rounded-full" title={t(`cat.${c}`)} style={{ background: cat(c).color }} />
                      ))}
                    </span>
                    <span>{a.signal_count} {t('list.sig')} · {a.source_count} {t('list.src')}</span>
                    <span className="ml-auto">{timeAgo(a.last_seen)}</span>
                  </div>
                </div>
                <div className="font-mono text-2xl font-semibold" style={{ color: l.color }}>{Math.round(a.score)}</div>
              </div>
            </button>
          )
        })}
        {hiddenOnMobile > 0 && (
          <button onClick={() => setShowAll((s) => !s)}
            className="w-full rounded-lg py-2.5 text-sm font-medium text-cyan-300 ring-1 ring-slate-700 hover:bg-slate-800/50 lg:hidden">
            {showAll ? t('list.showLess') : t('list.showAll', { n: alerts.length })}
          </button>
        )}
      </div>
    </div>
  )
}
