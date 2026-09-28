'use client'

import * as React from 'react'
import { Check, Pause, Play } from 'lucide-react'
import { cn } from '@/lib/utils'

/** A paper-frame flipbook. Decorative motion never pretends to measure review progress. */
export function ReviewWaiting({ compact = false }: { compact?: boolean }) {
  const [paused, setPaused] = React.useState(false)
  return (
    <div className={cn('review-waiting', compact && 'review-waiting-compact')}>
      <div className="review-flipbook" data-paused={paused} aria-hidden="true">
        <span className="review-paper paper-back" />
        <span className="review-paper paper-front"><span className="paper-picture" /><span className="paper-line" /><span className="paper-line short" /></span>
        <span className="review-stamp"><Check size={20} strokeWidth={3} /></span>
      </div>
      <div className="min-w-0 flex-1" role="status">
        <p className="text-[0.9375rem] font-semibold text-text-primary">A second pair of eyes.</p>
        <p className="mt-1 text-[0.8125rem] leading-relaxed text-text-secondary">Reviewing your file. Feedback will appear here.</p>
      </div>
      <button type="button" onClick={() => setPaused(v => !v)} aria-label={paused ? 'Play waiting animation' : 'Pause waiting animation'} className="motion-toggle press grid h-11 w-11 shrink-0 place-items-center rounded-full text-text-secondary hover:bg-bg-hover">
        {paused ? <Play size={16} /> : <Pause size={16} />}
      </button>
    </div>
  )
}
