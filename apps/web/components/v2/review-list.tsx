'use client'

import * as React from 'react'
import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import { timecode, type ReviewComment } from '@/lib/platform'

/**
 * The review as an editor reads it: what must be fixed first (serial position), then what is worth
 * a look. Each note is one sentence and, where it applies to a moment, a timestamp that jumps there.
 */
type Objector = (c: ReviewComment, text: string) => Promise<{ withdrawn: boolean; why: string }>

export function ReviewList({ comments, onSeek, onObject, empty = 'Nothing to fix. This one is good to go.' }: {
  comments: ReviewComment[]
  onSeek?: (t: number) => void
  /** When set, every must-fix gets a "Not right?" - the release valve, so a wrong note never traps anyone. */
  onObject?: Objector
  empty?: string
}) {
  const isMust = (c: ReviewComment) => c.must_fix || c.weight === 'must_fix'
  const must = comments.filter(isMust)
  const rest = comments.filter((c) => !isMust(c))
  if (!comments.length) {
    return (
      <div className="glass flex items-center gap-3 p-5 text-[15px] text-text-primary fade-in">
        <span className="grid h-8 w-8 place-items-center rounded-full bg-[rgba(48,209,88,0.14)] text-status-success"><Check className="h-4 w-4" /></span>
        {empty}
      </div>
    )
  }
  return (
    <div className="space-y-6">
      {must.length > 0 && <Group title="Must fix" hint="Fix these before it goes out." items={must} must onSeek={onSeek} onObject={onObject} />}
      {rest.length > 0 && <Group title="Worth a look" hint="Optional. Nothing here holds anything up." items={rest} onSeek={onSeek} />}
    </div>
  )
}

function Group({ title, hint, items, must, onSeek, onObject }: { title: string; hint: string; items: ReviewComment[]; must?: boolean; onSeek?: (t: number) => void; onObject?: Objector }) {
  return (
    <section>
      <div className="mb-2.5 flex items-baseline justify-between gap-3 px-1">
        <h3 className={cn('text-[13px] font-semibold uppercase tracking-[0.06em]', must ? 'text-status-error' : 'text-text-secondary')}>
          {title} · {items.length}
        </h3>
        <p className="hidden text-[13px] text-text-tertiary sm:block">{hint}</p>
      </div>
      <ol className="stagger space-y-2">
        {items.map((c, i) => (
          <li key={i} className={cn('flex gap-3 bg-bg-secondary p-4', must ? 'mustfix-ring' : 'rounded-[var(--radius-lg)] border border-border')}>
            {c.t !== null && c.t !== undefined ? (
              <button
                type="button"
                onClick={() => onSeek?.(c.t as number)}
                disabled={!onSeek}
                className="press h-7 shrink-0 rounded-full bg-bg-hover px-2.5 font-mono text-[12px] tabular-nums text-text-primary enabled:hover:bg-accent-muted enabled:hover:text-accent"
                aria-label={`Jump to ${timecode(c.t)}`}
              >
                {timecode(c.t)}
              </button>
            ) : (
              <span className="h-7 shrink-0 rounded-full bg-bg-tertiary px-2.5 text-[12px] leading-7 text-text-tertiary">Whole video</span>
            )}
            <div className="min-w-0 flex-1">
              <p className="text-[15px] leading-[1.45] text-text-primary">{c.body}</p>
              {must && onObject && <Dispute c={c} onObject={onObject} />}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

function Dispute({ c, onObject }: { c: ReviewComment; onObject: Objector }) {
  const [open, setOpen] = React.useState(false)
  const [text, setText] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const [answer, setAnswer] = React.useState<{ withdrawn: boolean; why: string } | null>(null)
  const [error, setError] = React.useState('')
  if (answer) {
    return (
      <p className={cn('mt-2 text-[13px] fade-in', answer.withdrawn ? 'text-status-success' : 'text-text-secondary')}>
        {answer.withdrawn ? 'Withdrawn. ' : ''}{answer.why}
      </p>
    )
  }
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="mt-2 text-[13px] font-medium text-text-secondary underline-offset-2 hover:text-text-primary hover:underline">
        Not right?
      </button>
    )
  }
  const send = async () => {
    setBusy(true); setError('')
    try { setAnswer(await onObject(c, text.trim())) }
    catch (e) { setError(e instanceof Error ? e.message : 'That did not send. Try again.') }
    finally { setBusy(false) }
  }
  return (
    <div className="mt-3 space-y-2 fade-in">
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} autoFocus
        placeholder="What is actually in the video? e.g. The price is on screen at 0:14."
        className="field min-h-[64px] resize-y py-2.5 text-[15px] leading-relaxed" aria-label="Why the note is wrong" />
      {error && <p className="text-[13px] text-status-error" role="alert">{error}</p>}
      <div className="flex justify-end gap-2">
        <button type="button" onClick={() => setOpen(false)} className="press h-10 rounded-full px-4 text-[13px] font-medium text-text-secondary hover:bg-bg-hover">Cancel</button>
        <button type="button" onClick={send} disabled={text.trim().length < 3 || busy}
          className="press h-10 rounded-full bg-bg-hover px-4 text-[13px] font-semibold text-text-primary disabled:text-text-tertiary">
          {busy ? 'Checking…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
