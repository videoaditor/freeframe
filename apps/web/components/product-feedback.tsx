'use client'

import { useRef, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { MessageSquare, X } from 'lucide-react'
import { usePathname } from 'next/navigation'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'

export function ProductFeedback() {
  const pathname = usePathname()
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
        <Button variant="ghost" size="lg" className="w-full justify-start px-3">
          <MessageSquare size={18} aria-hidden="true" />Give feedback
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60" />
        <Dialog.Content className="fixed inset-x-0 bottom-0 z-50 max-h-[90dvh] overflow-y-auto rounded-t-2xl border border-border bg-bg-secondary p-6 text-text-primary shadow-xl sm:inset-x-auto sm:inset-y-0 sm:right-0 sm:max-h-none sm:w-[440px] sm:rounded-none">
          <div className="flex items-center justify-between gap-4">
            <Dialog.Title className="text-[1.375rem] font-semibold leading-7">Give feedback</Dialog.Title>
            <Dialog.Close asChild><Button variant="ghost" size="lg" className="h-11 w-11 shrink-0 p-0" aria-label="Close feedback"><X size={20} /></Button></Dialog.Close>
          </div>
          <Dialog.Description className="mt-2 text-[1.0625rem] leading-6 text-text-secondary">
            Found a bug or have an idea? Help us improve AutoReview.
          </Dialog.Description>
          {receipt ? (
            <div role="status" className="mt-8 space-y-4">
              <h2 className="text-lg font-semibold">Feedback received</h2>
              <p className="text-text-secondary">Thanks. Your feedback is saved for our team to review.</p>
              <p className="break-all text-[0.8125rem] leading-[1.125rem] text-text-secondary">Receipt: {receipt}</p>
              <Dialog.Close asChild><Button size="lg">Done</Button></Dialog.Close>
            </div>
          ) : (
            <form onSubmit={submit} className="mt-6 space-y-6">
              <fieldset disabled={sending} className="space-y-3">
                <legend className="mb-2 text-sm font-medium">Feedback type</legend>
                {([['bug', 'Report a bug'], ['idea', 'Suggest an improvement']] as const).map(([value, label]) => (
                  <label key={value} className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md border border-border px-3 py-2 hover:bg-bg-hover">
                    <input type="radio" name="feedback-kind" value={value} checked={kind === value} onChange={() => setKind(value)} className="h-4 w-4 accent-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" />
                    <span>{label}</span>
                  </label>
                ))}
              </fieldset>
              <div>
                <label htmlFor="product-feedback-message" className="mb-2 block text-sm font-medium">Your feedback</label>
                <textarea id="product-feedback-message" value={message} onChange={event => setMessage(event.target.value)} required maxLength={4000} rows={5} disabled={sending} aria-describedby="product-feedback-help" className="w-full resize-y rounded-md border border-border bg-bg-primary p-3 text-[1.0625rem] leading-6 placeholder:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent" placeholder={kind === 'bug' ? 'What happened, and what did you expect?' : 'What would make your work easier?'} />
                <p id="product-feedback-help" className="mt-2 text-[0.8125rem] leading-[1.125rem] text-text-secondary">Please leave out passwords, patient details and private links. {message.length}/4000</p>
              </div>
              {error && <p role="alert" className="text-sm text-text-primary">We couldn&apos;t save your feedback. Your message is still here. Try again.</p>}
              <Button type="submit" size="lg" loading={sending} disabled={!message.trim()} className="w-full">{sending ? 'Saving feedback…' : 'Send feedback'}</Button>
            </form>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
