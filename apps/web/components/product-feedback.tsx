'use client'

import { useRef, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { MessageSquare, X, Bug, Lightbulb, ArrowUpRight, Check } from 'lucide-react'
import { usePathname } from 'next/navigation'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'

export function ProductFeedback() {
  const pathname = usePathname()
  const isViewer = /\/projects\/[^/]+\/assets\/[^/]+/.test(pathname)
  const [open, setOpen] = useState(false)
  const [kind, setKind] = useState<'bug' | 'idea'>('bug')
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(false)
  const [receipt, setReceipt] = useState<string | null>(null)
  const attempt = useRef<{ id: string; fingerprint: string } | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (sending || !message.trim()) return
    const payload = { kind, message: message.trim(), page_path: pathname }
    const fingerprint = JSON.stringify(payload)
    // A lost receipt can hide a committed report. Reuse its ID only for the
    // same payload, so an edited draft cannot be acknowledged as the old report.
    if (attempt.current?.fingerprint !== fingerprint) {
      attempt.current = { id: crypto.randomUUID(), fingerprint }
    }
    setSending(true)
    setError(false)
    try {
      const result = await api.post<{ id: string; status: 'received' }>('/product-feedback', {
        submission_id: attempt.current.id, ...payload,
      })
      setReceipt(result.id)
      setMessage('')
      attempt.current = null
    } catch {
      setError(true)
    } finally {
      setSending(false)
    }
  }

  function changeOpen(next: boolean) {
    if (next && receipt) { setReceipt(null); setError(false) }
    setOpen(next)
  }

  return (
    <Dialog.Root open={open} onOpenChange={changeOpen}>
      <Dialog.Trigger asChild>
        <Button variant="secondary" size="lg" aria-label="Give feedback" data-viewer={isViewer || undefined} className="feedback-launcher">
          <MessageSquare size={19} aria-hidden="true" /><span>Feedback</span>
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="feedback-overlay fixed inset-0 z-50 bg-black/30" />
        <Dialog.Content className="feedback-panel fixed inset-x-0 bottom-0 z-50 max-h-[90dvh] overflow-y-auto rounded-t-3xl border border-border bg-bg-secondary p-6 text-text-primary shadow-xl sm:inset-x-auto sm:bottom-6 sm:right-6 sm:w-[400px] sm:rounded-3xl">
          <div className="flex items-center justify-between gap-4">
            <div><p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-text-secondary">Your input matters</p><Dialog.Title className="text-[1.375rem] font-semibold leading-7 tracking-tight">Help shape AutoReview</Dialog.Title></div>
            <Dialog.Close asChild><Button variant="ghost" size="lg" className="h-11 w-11 shrink-0 p-0" aria-label="Close feedback"><X size={20} /></Button></Dialog.Close>
          </div>
          <Dialog.Description className="mt-2 text-[1.0625rem] leading-6 text-text-secondary">
            What would make AutoReview better for you?
          </Dialog.Description>
          {receipt ? (
            <div role="status" className="mt-8 space-y-4">
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-accent/10 text-accent"><Check size={24} aria-hidden="true" /></div><h2 className="text-lg font-semibold">Feedback received</h2>
              <p className="text-text-secondary">Thanks. Your feedback is saved for our team to review.</p>
              <p className="break-all text-[0.8125rem] leading-[1.125rem] text-text-secondary">Receipt: {receipt}</p>
              <Dialog.Close asChild><Button size="lg">Done</Button></Dialog.Close>
            </div>
          ) : (
            <form onSubmit={submit} className="mt-5 space-y-5">
              <fieldset disabled={sending} className="grid grid-cols-2 gap-3">
                <legend className="sr-only">Feedback type</legend>
                {([['bug', 'Report a bug', Bug], ['idea', 'Feature request', Lightbulb]] as const).map(([value, label, Icon]) => (
                  <label key={value} className={`feedback-kind relative flex min-h-[88px] cursor-pointer flex-col gap-3 rounded-2xl border p-3 text-sm transition-colors ${kind === value ? 'border-accent bg-accent/10' : 'border-border hover:bg-bg-hover'}`}>
                    <input type="radio" name="feedback-kind" value={value} checked={kind === value} onChange={() => setKind(value)} className="absolute right-3 top-3 h-4 w-4 accent-accent" />
                    <Icon size={20} aria-hidden="true" /><span className="font-medium">{label}</span>
                  </label>
                ))}
              </fieldset>
              <div>
                <label htmlFor="product-feedback-message" className="mb-2 block text-sm font-medium">Your feedback</label>
                <textarea id="product-feedback-message" value={message} onChange={event => setMessage(event.target.value)} required maxLength={4000} rows={4} disabled={sending} aria-describedby="product-feedback-help" className="w-full resize-y rounded-xl border border-border bg-bg-primary p-3 text-[1.0625rem] leading-6 placeholder:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent" placeholder={kind === 'bug' ? 'What happened, and what did you expect?' : 'What would make your work easier?'} />
                <p id="product-feedback-help" className="mt-2 text-[0.8125rem] leading-[1.125rem] text-text-secondary">Please leave out passwords, patient details and private links. {message.length}/4000</p>
              </div>
              {error && <p role="alert" className="text-sm text-text-primary">We couldn&apos;t save your feedback. Your message is still here. Try again.</p>}
              <Button type="submit" size="lg" loading={sending} disabled={!message.trim()} className="w-full">{sending ? 'Saving feedback…' : <>Send feedback<ArrowUpRight size={18} aria-hidden="true" /></>}</Button>
            </form>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
