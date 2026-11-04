'use client'

import * as React from 'react'
import { METER_COLUMNS, METER_ROWS, columnRows, pushLevel } from '@/lib/level-meter'

/** Dot-matrix level: columns of dots, newest on the right, fading out to the left. Static under reduced motion. */
export function LevelMeter({ levelRef, active = true }: { levelRef: React.MutableRefObject<number>; active?: boolean }) {
  const [history, setHistory] = React.useState<number[]>(() => Array.from({ length: METER_COLUMNS }, () => 0.15))
  const reduced = typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  React.useEffect(() => {
    if (!active || reduced) return
    const id = setInterval(() => setHistory(h => pushLevel(h, levelRef.current)), 70)
    return () => clearInterval(id)
  }, [active, reduced, levelRef])
  const columns = reduced ? Array.from({ length: METER_COLUMNS }, (_, i) => 0.25 + ((i * 7) % 5) / 12) : history
  return (
    <div data-testid="level-meter" aria-hidden="true" className="flow-meter flex h-14 min-w-0 flex-1 items-center justify-center gap-1">
      {columns.map((lv, c) => {
        const rows = columnRows(lv, METER_ROWS)
        return (
          <div key={c} className="flex flex-col gap-1">
            {rows.map((on, r) => <span key={r} data-lit={on ? '' : undefined} className="block h-1 w-1 rounded-full bg-text-tertiary/25 data-[lit]:bg-text-primary" />)}
          </div>
        )
      })}
    </div>
  )
}
