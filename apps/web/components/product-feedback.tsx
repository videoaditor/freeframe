'use client'

import { useRef, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { MessageSquare, X, Bug, Lightbulb, ArrowUp, Check, Mic, Square, Trash2 } from 'lucide-react'
import { usePathname } from 'next/navigation'
import { api } from '@/lib/api'
import { useFeedbackRecording } from '@/hooks/use-feedback-recording'
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
  const voice = useFeedbackRecording(text => setMessage(current => [current.trim(), text].filter(Boolean).join('\n\n')))
  const attempt = useRef<{ id: string; fingerprint: string } | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (sending || voice.busy || voice.unsaved || message.length > 4000 || (!message.trim() && !voice.recordingId)) return
    const payload = { kind, message: message.trim(), page_path: pathname, ...(voice.recordingId ? { recording_id: voice.recordingId } : {}) }
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
      voice.reset()
      attempt.current = null
    } catch {
      setError(true)
    } finally {
      setSending(false)
    }
  }

  function changeOpen(next: boolean) {
    if (next && receipt) { setReceipt(null); setError(false) }
    if (!next) voice.stop()
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
        <Dialog.Content className="feedback-panel fixed inset-x-0 bottom-0 z-50 max-h-[90dvh] overflow-y-auto rounded-t-3xl border border-border bg-bg-secondary p-5 text-text-primary shadow-xl sm:inset-x-auto sm:bottom-6 sm:right-6 sm:w-[360px] sm:rounded-2xl">
          <div className="flex items-start justify-between gap-2">
            <Dialog.Title className="pt-1 text-xl font-semibold leading-[1.3] tracking-tight">What can we build to make this the best it can be?</Dialog.Title>
            <Dialog.Close asChild><Button variant="ghost" size="lg" className="-mr-2 -mt-2 h-11 w-11 shrink-0 p-0" aria-label="Close feedback"><X size={18} /></Button></Dialog.Close>
          </div>
          <Dialog.Description className="mt-3 text-sm leading-5 text-text-secondary">
            Our tech team is highly caffeinated and doesn’t take holidays.
          </Dialog.Description>
          {receipt ? (
            <div role="status" className="mt-6 space-y-3">
              <div className="flex items-center gap-2"><Check size={20} className="text-accent" aria-hidden="true" /><h2 className="font-semibold">Feedback received</h2></div>
              <p className="text-sm text-text-secondary">It’s saved. Let’s make something better.</p>
              <Dialog.Close asChild><Button size="lg">Done</Button></Dialog.Close>
            </div>
          ) : (
            <form onSubmit={submit} className="mt-4 space-y-4">
              <fieldset disabled={sending} className="inline-flex rounded-xl bg-bg-primary p-1">
                <legend className="sr-only">Feedback type</legend>
                {([['bug', 'Bug', Bug], ['idea', 'Feature', Lightbulb]] as const).map(([value, label, Icon]) => (
                  <label key={value} className={`feedback-kind relative inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-lg px-4 text-sm transition-colors ${kind === value ? 'bg-bg-secondary font-medium shadow-sm' : 'text-text-secondary hover:bg-bg-hover'}`}>
                    <input type="radio" name="feedback-kind" value={value} checked={kind === value} onChange={() => setKind(value)} className="sr-only" />
                    <Icon size={16} aria-hidden="true" /><span>{label}</span>
                  </label>
                ))}
              </fieldset>
              <div>
                <label htmlFor="product-feedback-message" className="sr-only">Your feedback</label>
                <textarea id="product-feedback-message" value={message} onChange={event => setMessage(event.target.value)} required={!voice.recordingId} maxLength={4000} rows={3} disabled={sending} aria-describedby="product-feedback-help" className="block w-full resize-y rounded-xl border border-border bg-bg-primary p-3 text-base leading-6 placeholder:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent" placeholder={kind === 'bug' ? 'What’s not working?' : 'What should we build next?'} />
                <p id="product-feedback-help" className="mt-2 text-xs leading-4 text-text-secondary">No passwords or patient info.{message.length > 3600 && ` ${message.length}/4000`}</p>
              </div>
              {voice.audioUrl && <div className="space-y-2">
                <div className="flex items-center gap-2"><audio aria-label="Your voice note" controls src={voice.audioUrl} className="h-10 min-w-0 flex-1" /><Button type="button" variant="ghost" className="h-11 w-11 shrink-0 p-0" aria-label="Remove voice note" disabled={voice.busy || sending} onClick={voice.reset}><Trash2 size={16} /></Button></div>
                {voice.unsaved && !voice.busy && <Button type="button" variant="secondary" size="lg" onClick={() => void voice.retry()}>Retry saving audio</Button>}
              </div>}
              {voice.note && <p role="status" className="text-xs leading-4 text-text-secondary">{voice.note}</p>}
              {voice.error && <p role="alert" className="text-sm">{voice.error}</p>}
              {error && <p role="alert" className="text-sm">We couldn&apos;t save your feedback. Your message is still here. Try again.</p>}
              {message.length > 4000 && <p role="alert" className="text-sm">Please shorten the text to 4,000 characters. Your audio stays attached.</p>}
              <div className="flex items-center justify-between gap-3">
                {voice.phase === 'recording' || voice.phase === 'starting' ? (
                  <Button type="button" variant="secondary" size="lg" onClick={voice.stop}><Square size={12} aria-hidden="true" />{voice.phase === 'recording' && <span aria-hidden="true" className="feedback-wave flex h-5 items-center gap-[2px]">{[.35, .65, .85, 1, .85, .65, .35].map((weight, index) => <span key={index} className="h-5 w-[3px] rounded-full bg-current transition-transform duration-100 ease-out motion-reduce:!transform-none motion-reduce:!h-1" style={{ transform: `scaleY(${.15 + (voice.level || 0) * .85 * weight})` }} />)}</span>}{voice.phase === 'starting' ? 'Cancel' : `Stop · ${Math.floor(voice.seconds / 60)}:${String(voice.seconds % 60).padStart(2, '0')}`}</Button>
                ) : <Button type="button" variant="ghost" size="lg" className="-ml-2 px-2" disabled={sending || voice.busy || Boolean(voice.audioUrl)} onClick={() => void voice.start()}><Mic size={17} aria-hidden="true" />{voice.phase === 'uploading' ? 'Saving audio…' : voice.phase === 'transcribing' ? 'Dictating…' : 'Dictate'}</Button>}
                <Button type="submit" size="lg" loading={sending} aria-label={sending ? 'Saving feedback…' : 'Send feedback'} disabled={voice.busy || voice.unsaved || message.length > 4000 || (!message.trim() && !voice.recordingId)}>{sending ? 'Sending…' : <>Send<ArrowUp size={17} aria-hidden="true" /></>}</Button>
              </div>
              <p className="text-xs leading-4 text-text-secondary">Your recording is saved with your feedback. Up to 2 min.</p>
            </form>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
