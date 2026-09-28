import { cn } from '@/lib/utils'

const TONE = {
  neutral: 'bg-bg-hover text-text-secondary',
  progress: 'bg-accent-muted text-accent',
  warn: 'bg-[rgba(255,214,10,0.12)] text-status-warning',
  ok: 'bg-[rgba(48,209,88,0.12)] text-status-success',
} as const

const DOT = {
  neutral: 'bg-text-tertiary',
  progress: 'bg-accent animate-pulse-soft',
  warn: 'bg-status-warning',
  ok: 'bg-status-success',
} as const

/** Status the Aditor way: a dot and words in a soft pill. Never colour alone (HIG). */
export function StatusPill({ label, tone }: { label: string; tone: keyof typeof TONE }) {
  return (
    <span data-tone={tone} className={cn('inline-flex h-7 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-[13px] font-medium', TONE[tone])}>
      <span className={cn('h-1.5 w-1.5 rounded-full', DOT[tone])} aria-hidden="true" />
      {label}
    </span>
  )
}
