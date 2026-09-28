'use client'

/**
 * Time saved (platform v2 "finance" screen).
 *
 * Alan, 2026-09-28: how long watching every uploaded video would have taken, plus how long typing
 * the review comments would have taken. One hero number (the headline), one 30-day series, one bar
 * per brand. The assumptions are printed under the number - a figure nobody can check is a figure
 * nobody trusts.
 */
import * as React from 'react'
import useSWR from 'swr'
import { usePageTitle } from '@/hooks/use-page-title'
import { getTimeSaved, hours, humanDuration, type TimeSaved } from '@/lib/platform'
import { cn } from '@/lib/utils'

const RANGES = [7, 30, 90] as const

export default function InsightsPage() {
  usePageTitle('Time saved')
  const [days, setDays] = React.useState<(typeof RANGES)[number]>(30)
  const { data, error, isLoading } = useSWR<TimeSaved>(`/insights/time-saved?${days}`, () => getTimeSaved(days))

  return (
    <div className="page-in mx-auto w-full max-w-5xl px-4 pb-20 pt-8 sm:px-8 sm:pt-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-[34px] font-bold leading-tight tracking-[-0.02em] text-text-primary">Time saved</h1>
        {/* One row of filters above the chart (dataviz: filters live together, above). */}
        <div role="radiogroup" aria-label="Period" className="inline-flex rounded-full border border-border bg-bg-secondary p-1">
          {RANGES.map((d) => (
            <button key={d} type="button" role="radio" aria-checked={days === d} onClick={() => setDays(d)}
              className={cn('press h-9 rounded-full px-4 text-[13px] font-medium transition-colors',
                days === d ? 'bg-bg-hover text-text-primary' : 'text-text-secondary hover:text-text-primary')}>
              {d} days
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <p className="mt-10 text-[15px] text-status-error">The numbers are not reachable right now. Try again in a minute.</p>
      ) : isLoading || !data ? (
        <div className="mt-8 space-y-4">
          <div className="skeleton-shimmer h-44 animate-shimmer rounded-[var(--radius-xl)]" />
          <div className="skeleton-shimmer h-72 animate-shimmer rounded-[var(--radius-xl)]" />
        </div>
      ) : (
        <>
          <section className="glass mt-8 p-6 sm:p-8">
            <p className="text-[15px] text-text-secondary">Estimated review time saved · last {data.days} days</p>
            <p className="mt-2 flex items-baseline gap-2">
              <span className="text-[64px] font-semibold leading-none tracking-[-0.03em] text-text-primary sm:text-[80px]">{hours(data.totalSec)}</span>
              <span className="text-[22px] font-medium text-text-secondary">hours</span>
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <Stat label="Watching every video once" value={humanDuration(data.watchSec)} />
              <Stat label="Typing the feedback" value={humanDuration(data.typeSec)} />
              <Stat label="Videos reviewed" value={data.videos.toLocaleString()} />
            </div>
            <p className="mt-5 text-[13px] leading-relaxed text-text-tertiary">
              How we count: one full watch of every reviewed version, plus every word of feedback typed at {data.assumptions.wpm} words per minute.
              This estimates manual review effort; actual time saved varies.
            </p>
          </section>

          <section className="mt-6 rounded-[var(--radius-xl)] border border-border bg-bg-secondary p-6 sm:p-8">
            <h2 className="text-[17px] font-semibold tracking-tight text-text-primary">Per day</h2>
            <p className="text-[13px] text-text-secondary">Hours saved</p>
            <DailyChart points={data.perDay} />
          </section>

          {data.perBrand.length > 0 && (
            <section className="mt-6 rounded-[var(--radius-xl)] border border-border bg-bg-secondary p-6 sm:p-8">
              <h2 className="text-[17px] font-semibold tracking-tight text-text-primary">By brand</h2>
              <BrandBars rows={data.perBrand} />
            </section>
          )}
        </>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-border bg-bg-primary/40 px-4 py-3">
      <p className="text-[13px] text-text-secondary">{label}</p>
      <p className="mt-0.5 text-[20px] font-semibold tracking-tight text-text-primary">{value}</p>
    </div>
  )
}

/** Area line, one series, orange: 2px line, ~10% wash, hairline grid, crosshair + tooltip on hover. */
function DailyChart({ points }: { points: { day: string; sec: number }[] }) {
  // Drawn at the container's real pixel width, so text and 2px lines stay 12px and 2px on any screen.
  const wrap = React.useRef<HTMLDivElement>(null)
  const [W, setW] = React.useState(880)
  React.useEffect(() => {
    const el = wrap.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, Math.round(e.contentRect.width))))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  const H = W < 560 ? 200 : 260, P = { l: 36, r: 12, t: 16, b: 28 }
  const [hover, setHover] = React.useState<number | null>(null)
  const svgRef = React.useRef<SVGSVGElement>(null)
  if (!points.length) return null
  const vals = points.map((p) => p.sec / 3600)
  const max = Math.max(1, ...vals)
  const step = niceStep(max)
  const top = Math.ceil(max / step) * step
  const x = (i: number) => P.l + (i * (W - P.l - P.r)) / Math.max(1, points.length - 1)
  const y = (v: number) => P.t + (1 - v / top) * (H - P.t - P.b)
  const line = vals.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')
  const area = `${line}L${x(vals.length - 1)},${y(0)}L${x(0)},${y(0)}Z`
  const ticks = Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step)
  const label = (d: string) => new Date(d + 'T12:00:00Z').toLocaleDateString(undefined, { day: 'numeric', month: 'short' })

  const onMove = (e: React.PointerEvent) => {
    const r = svgRef.current?.getBoundingClientRect()
    if (!r) return
    const px = ((e.clientX - r.left) / r.width) * W
    const i = Math.round(((px - P.l) / (W - P.l - P.r)) * (points.length - 1))
    setHover(Math.max(0, Math.min(points.length - 1, i)))
  }
  const hv = hover !== null ? vals[hover] : null

  return (
    <div ref={wrap} className="relative mt-4">
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="block max-w-full touch-none" role="img"
        aria-label={`Hours saved per day, highest ${max.toFixed(1)} hours`}
        onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} stroke="var(--border-secondary)" strokeWidth="1" />
            <text x={P.l - 8} y={y(t) + 4} textAnchor="end" fontSize="12" fill="var(--text-tertiary)">{Number(t.toFixed(2))}</text>
          </g>
        ))}
        {[0, Math.floor((points.length - 1) / 2), points.length - 1].map((i) => (
          <text key={i} x={x(i)} y={H - 8} textAnchor={i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle'} fontSize="12" fill="var(--text-tertiary)">
            {label(points[i].day)}
          </text>
        ))}
        <path d={area} fill="var(--accent)" opacity="0.1" />
        <path d={line} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {hover !== null && hv !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={P.t} y2={y(0)} stroke="var(--text-tertiary)" strokeWidth="1" />
            <circle cx={x(hover)} cy={y(hv)} r="5" fill="var(--accent)" stroke="var(--bg-secondary)" strokeWidth="2" />
          </g>
        )}
      </svg>
      {hover !== null && hv !== null && (
        <div className="pointer-events-none absolute top-0 -translate-x-1/2 rounded-[var(--radius-md)] border border-border bg-bg-elevated px-3 py-2 shadow-lg"
          style={{ left: `${(x(hover) / W) * 100}%` }}>
          <p className="text-[12px] text-text-secondary">{label(points[hover].day)}</p>
          <p className="text-[15px] font-semibold tabular-nums text-text-primary">{humanDuration(points[hover].sec)}</p>
        </div>
      )}
      {/* The table view: every value, readable without the chart. */}
      <details className="mt-3">
        <summary className="cursor-pointer text-[13px] text-text-secondary hover:text-text-primary">Show as table</summary>
        <table className="mt-2 w-full text-left text-[13px]">
          <tbody>
            {points.filter((p) => p.sec > 0).map((p) => (
              <tr key={p.day} className="border-t border-border"><td className="py-1.5 text-text-secondary">{label(p.day)}</td><td className="py-1.5 text-right tabular-nums text-text-primary">{humanDuration(p.sec)}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}

/** Horizontal bars, one measure: 24px max thickness, 4px rounded tip, value at the tip in text ink. */
function BrandBars({ rows }: { rows: { brand: string; sec: number; videos: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.sec))
  return (
    <ul className="mt-5 space-y-3">
      {rows.slice(0, 12).map((r) => (
        <li key={r.brand} className="group grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)] items-center gap-4" title={`${r.brand}: ${humanDuration(r.sec)} over ${r.videos} videos`}>
          <span className="truncate text-[13px] text-text-secondary">{brandName(r.brand)}</span>
          <span className="flex items-center gap-3">
            <span className="h-5 rounded-r-[4px] bg-accent transition-opacity group-hover:opacity-80" style={{ width: `${Math.max(2, (r.sec / max) * 100)}%` }} />
            <span className="shrink-0 whitespace-nowrap text-[13px] tabular-nums text-text-primary">{humanDuration(r.sec)}</span>
          </span>
        </li>
      ))}
    </ul>
  )
}

function niceStep(max: number): number {
  const raw = max / 4
  const mag = Math.pow(10, Math.floor(Math.log10(raw)))
  const n = raw / mag
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag
}

/** "keller-gesundheit" -> "Keller Gesundheit". The slug is the key, not the name people know. */
function brandName(slug: string): string {
  if (!slug) return 'Unassigned'
  return slug.split('-').map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w)).join(' ')
}
