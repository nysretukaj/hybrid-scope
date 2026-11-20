import { VERIFICATION, cat, level, timeAgo } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { HybridBadge, LevelBadge, LiveBadge } from './ui'

/** The alerts, most dangerous first. Tap one to open its own page. */
export default function AlertList({ alerts, onSelect, total }) {
  const { t } = useI18n()
  return (
    <div className="panel">
      <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2.5">
        <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{t('list.title')}</span>
        <span className="font-mono text-[11px] text-slate-500">{alerts.length}/{total}</span>
      </div>
      <div className="space-y-1.5 p-2">
        {alerts.length === 0 && <div className="p-6 text-center text-sm text-slate-500">{t('list.none')}</div>}
        {alerts.map((a) => {
          const l = level(a.level)
          const verdict = a.verification || 'unverified'
          const vstyle = VERIFICATION[verdict]
          return (
            <button
              key={a.id}
              onClick={() => onSelect(a.id)}
              className={`group relative w-full overflow-hidden rounded-lg bg-slate-900/40 py-3 pl-4 pr-3 text-left ring-1 ring-slate-800 transition hover:bg-slate-800/50 hover:ring-slate-700 ${verdict === 'disproved' ? 'opacity-50' : ''}`}
            >
              <span className="absolute inset-y-0 left-0 w-1" style={{ background: l.color }} />
              <div className="flex items-center gap-3">
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
                  <div className="mt-1.5 truncate text-base font-medium text-slate-100">{a.zone_label || a.zone}</div>
                  <div className="truncate text-xs text-slate-400" title={a.headline}>{a.headline}</div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
                    <span className="font-medium" style={{ color: l.color }}>→ {t(`lv.${a.level}`)}</span>
                    <span className="flex gap-1">
                      {a.categories.map((c) => (
                        <span key={c} className="h-2 w-2 rounded-full" title={t(`cat.${c}`)} style={{ background: cat(c).color }} />
                      ))}
                    </span>
                    <span className="ml-auto text-slate-500">{timeAgo(a.last_seen)}</span>
                  </div>
                </div>
                <div className="font-mono text-2xl font-semibold" style={{ color: l.color }}>{Math.round(a.score)}</div>
                <span className="text-xl text-slate-600 group-hover:text-slate-300" aria-hidden>›</span>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
