'use client'

import * as React from 'react'
import { Check, RotateCcw, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatBytes } from '@/lib/platform'
import { FolderArt } from './folder-art'

export type UploadPhase = 'uploading' | 'reviewing' | 'done' | 'error'

/** The number counts up to the real value instead of jumping - the upload feels continuous. */
function useEased(target: number) {
  const [v, setV] = React.useState(target)
  React.useEffect(() => {
    let raf = 0
    const tick = () => {
      setV((cur) => {
        const next = cur + (target - cur) * 0.18
        if (Math.abs(target - next) < 0.2) return target
        raf = requestAnimationFrame(tick)
        return next
      })
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target])
  return v
}

const PHASE_TEXT: Record<UploadPhase, string> = {
  uploading: 'Uploading',
  reviewing: 'Reviewing, about a minute',
  done: 'Reviewed',
  error: 'Stopped',
}

export function UploadCard({ name, size, progress, phase, error, onRetry, onRemove, className }: {
  name: string
  size: number
  progress: number
  phase: UploadPhase
  error?: string
  onRetry?: () => void
  onRemove?: () => void
  className?: string
}) {
  const pct = useEased(Math.round(Math.min(1, Math.max(0, progress)) * 100))
  return (
    <div className={cn('glass p-5 sm:p-6', phase === 'reviewing' && 'scan', className)} role="status" aria-live="polite">
      <div className="flex items-center gap-4">
        <FolderArt size={64} label={phase === 'done' ? 'DONE' : 'FILE'} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[17px] font-semibold tracking-tight text-text-primary">{name}</p>
          <p className="mt-0.5 text-[13px] text-text-secondary">{formatBytes(size)}</p>
        </div>
        {onRemove && phase !== 'uploading' && (
          <button type="button" onClick={onRemove} aria-label="Remove" className="press grid h-11 w-11 place-items-center rounded-full text-text-tertiary hover:bg-bg-hover hover:text-text-primary">
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
      <div className="mt-5 rounded-[var(--radius-lg)] border border-border bg-bg-primary/40 px-4 py-3.5">
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-2 text-[15px] text-text-primary">
            {phase === 'done' ? <Check className="h-4 w-4 text-status-success" /> :
             phase === 'error' ? <span className="h-2 w-2 rounded-full bg-status-error" /> :
             <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-text-tertiary border-t-accent" />}
            {PHASE_TEXT[phase]}{phase === 'uploading' ? '…' : ''}
          </span>
          {phase === 'uploading' && (
            <span className="text-[28px] font-light leading-none tabular-nums tracking-tight text-text-primary">{Math.round(pct)}%</span>
          )}
          {phase === 'error' && onRetry && (
            <button type="button" onClick={onRetry} className="press inline-flex h-9 items-center gap-1.5 rounded-full bg-bg-hover px-3.5 text-[13px] font-medium text-text-primary">
              <RotateCcw className="h-3.5 w-3.5" /> Try again
            </button>
          )}
        </div>
        {(phase === 'uploading' || phase === 'reviewing') && (
          <div className="progress-track mt-3">
            <div className="progress-fill" style={{ width: phase === 'reviewing' ? '100%' : `${pct}%` }} />
          </div>
        )}
        {phase === 'error' && error && <p className="mt-2 text-[13px] text-status-error">{error}</p>}
      </div>
    </div>
  )
}
