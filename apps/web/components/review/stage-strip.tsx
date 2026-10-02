'use client'

import * as React from 'react'
import { AlertCircle, CheckCircle2, ChevronRight, Circle, HelpCircle, Loader2, MinusCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { StageState, StageStep, StageView } from '@/lib/stages'

const ICON: Record<StageState, { icon: React.ReactNode; className: string }> = {
  done: { icon: <CheckCircle2 className="h-3.5 w-3.5" />, className: 'text-status-success' },
  active: { icon: <Loader2 className="h-3.5 w-3.5 animate-spin" />, className: 'text-status-warning' },
  waiting: { icon: <Circle className="h-3.5 w-3.5" />, className: 'text-text-tertiary' },
  failed: { icon: <AlertCircle className="h-3.5 w-3.5" />, className: 'text-status-error' },
  unknown: { icon: <HelpCircle className="h-3.5 w-3.5" />, className: 'text-text-tertiary' },
  skipped: { icon: <MinusCircle className="h-3.5 w-3.5" />, className: 'text-text-tertiary' },
}

function stepText(s: StageStep): string {
  const parts: string[] = []
  // A finished step needs no caption, except Done itself: "Reviewed: nothing to fix" IS its content.
  if (s.detail && (s.state !== 'done' || s.key === 'done')) parts.push(s.detail)
  if (s.minutes !== undefined && s.state === 'active') parts.push(`${s.minutes} min`)
  return parts.join(', ')
}

/**
 * Upload > Processing > Reviewing > Done, with the current step highlighted and how long it has run.
 *
 * Only draws what `computeStages` decided; it holds no logic of its own. `hideProblem` exists for
 * screens that already show the same message elsewhere (the hand-in page's failure notice).
 */
export function StageStrip({
  view,
  className,
  hideProblem = false,
}: {
  view: StageView
  className?: string
  hideProblem?: boolean
}) {
  return (
    <div data-testid="stage-strip" className={cn('text-xs', className)}>
      <ol aria-label="Progress" className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
        {view.steps.map((s, i) => {
          const cfg = ICON[s.state]
          const text = stepText(s)
          return (
            <React.Fragment key={s.key}>
              {i > 0 && <ChevronRight aria-hidden className="h-3 w-3 text-text-tertiary" />}
              <li
                data-testid={`stage-step-${s.key}`}
                data-state={s.state}
                aria-current={s.state === 'active' ? 'step' : undefined}
                className={cn(
                  'inline-flex items-center gap-1 rounded-md px-1.5 py-0.5',
                  s.state === 'active' && 'bg-bg-hover',
                )}
              >
                <span className={cfg.className}>{cfg.icon}</span>
                <span
                  className={cn(
                    s.state === 'waiting' || s.state === 'skipped' || s.state === 'unknown'
                      ? 'text-text-tertiary'
                      : 'text-text-primary',
                    s.state === 'active' && 'font-medium',
                  )}
                >
                  {s.label}
                </span>
                {text && <span className="text-text-tertiary">{text}</span>}
              </li>
            </React.Fragment>
          )
        })}
      </ol>
      <p className="sr-only" aria-live="polite">
        {view.headline}
      </p>
      {view.problem && !hideProblem && (
        <p
          data-testid="stage-problem"
          data-kind={view.problem.kind}
          role={view.problem.kind === 'failed' ? 'alert' : 'status'}
          className={cn('mt-1.5', view.problem.kind === 'failed' ? 'text-status-error' : 'text-status-warning')}
        >
          {view.problem.message}
        </p>
      )}
    </div>
  )
}
