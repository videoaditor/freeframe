'use client'

/**
 * "Here's your link" - the peak of the owner's flow, so it gets the one flourish.
 *
 * The whole card is the button (Fitts): tap anywhere to copy. Copying fills the card with a soft
 * orange wash from left to right and the icon morphs to a check - the confirmation is the card
 * itself, not a toast somewhere else. On a phone, Share hands it to the system sheet.
 */
import * as React from 'react'
import { Check, Copy, ExternalLink, Share } from 'lucide-react'
import { cn } from '@/lib/utils'

async function copyText(text: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(text); return true } catch { /* insecure context or denied */ }
  const t = document.createElement('textarea')
  t.value = text; t.setAttribute('readonly', ''); t.style.position = 'fixed'; t.style.opacity = '0'
  document.body.appendChild(t); t.select()
  try { return document.execCommand('copy') } catch { return false } finally { document.body.removeChild(t) }
}

export function prettyUrl(url: string): { host: string; path: string } {
  try { const u = new URL(url); return { host: u.host, path: u.pathname + u.search } } catch { return { host: url, path: '' } }
}

export function LinkCard({ url, label = 'Here’s your link', hint = 'Tap to copy', copiedHint = 'Copied. Paste it to your editor.' }: {
  url: string; label?: string; hint?: string; copiedHint?: string
}) {
  const [error, setError] = React.useState(false)
  const [copied, setCopied] = React.useState(false)
  const timer = React.useRef<ReturnType<typeof setTimeout>>()
  const { host, path } = prettyUrl(url)
  const canShare = typeof navigator !== 'undefined' && 'share' in navigator

  const copy = async () => {
    setError(false)
    if (await copyText(url)) {
      setCopied(true)
      clearTimeout(timer.current)
      timer.current = setTimeout(() => setCopied(false), 2400)
    } else { setError(true) }
  }
  React.useEffect(() => () => clearTimeout(timer.current), [])

  return (
    <div className="space-y-3">
      <button type="button" onClick={copy} aria-label={copied ? 'Link copied' : `Copy link ${url}`}
        className="link-card press group relative block w-full overflow-hidden rounded-[var(--radius-xl)] border border-[var(--glass-border)] bg-bg-tertiary p-5 text-left outline-none focus-visible:ring-2 focus-visible:ring-accent/60 sm:p-6">
        <span className="link-fill" data-on={copied} aria-hidden="true" />
        <span className="relative block text-[13px] font-semibold uppercase tracking-[0.06em] text-accent">{label}</span>
        <span className="relative mt-2 flex items-center gap-4">
          <span className="min-w-0 flex-1 truncate text-[20px] font-semibold tracking-tight sm:text-[22px]">
            <span className="text-text-secondary">{host}</span><span className="text-text-primary">{path}</span>
          </span>
          <span className={cn('grid h-12 w-12 shrink-0 place-items-center rounded-full transition-colors duration-200',
            copied ? 'bg-status-success text-[#04210c]' : 'bg-accent text-text-inverse group-hover:bg-accent-hover')}>
            <span key={copied ? 'c' : 'k'} className="icon-swap">{copied ? <Check className="h-5 w-5" strokeWidth={2.5} /> : <Copy className="h-5 w-5" />}</span>
          </span>
        </span>
        <span className="relative mt-2 block text-[13px] text-text-secondary" aria-live="polite">{copied ? copiedHint : hint}</span>
      </button>
      {error && <p role="alert" className="break-all text-[13px] text-status-error">Could not copy. Select this link: {url}</p>}
      <div className="flex gap-2">
        <a href={url} target="_blank" rel="noreferrer" className="press inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-full border border-border text-[15px] font-medium text-text-primary hover:bg-bg-hover">
          <ExternalLink className="h-4 w-4" /> Open as editor
        </a>
        {canShare && (
          <button type="button" onClick={() => navigator.share({ url }).catch(() => {})} className="press inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-full border border-border text-[15px] font-medium text-text-primary hover:bg-bg-hover">
            <Share className="h-4 w-4" /> Share
          </button>
        )}
      </div>
    </div>
  )
}
