'use client'

/**
 * The note to the client on a hand-in (Nico and Shawn, 2026-11-04). It goes out with the delivery: the
 * portal sends that and holds the note, FreeFrame stores nothing (`/r/<token>/note`). Saved as the
 * editor types, editable until the delivery goes out, and it says so plainly when that moment has passed.
 */

import * as React from 'react'
import useSWR from 'swr'
import { readDeliveryNote, saveDeliveryNote, type DeliveryNoteState } from '@/lib/platform'

export const DELIVERY_NOTE_MAX = 500

const SAVE_AFTER_MS = 1200

export const NOTE_COPY = {
  en: {
    label: 'Note for the client (optional)',
    placeholder: 'For example: 2 versions, A with still poses, B fully animated.',
    hint: 'Goes to the client with your delivery, exactly as you write it. You can change it until the delivery goes out, about 15 minutes after your last file.',
    laterHint: 'Goes to the client as a comment on the card, about 15 minutes after your last file.',
    saving: 'Saving…',
    saved: 'Saved. It goes out with the delivery.',
    tooLate: 'Too late: this card has already gone to the client, so this note was not sent and nothing new was posted.',
    closed: 'This card is already with the client. A note can go with its next version.',
    sent: 'Sent to the client:',
    failed: 'The note could not be saved. Try again.',
    noRoute: "This card's client does not get notes from here, so your note was not sent.",
  },
  de: {
    label: 'Notiz für den Kunden (optional)',
    placeholder: 'Zum Beispiel: 2 Versionen, A mit festen Posen, B voll animiert.',
    hint: 'Geht mit deiner Lieferung an den Kunden, genau so, wie du sie schreibst. Du kannst sie ändern, bis die Lieferung rausgeht, etwa 15 Minuten nach deiner letzten Datei.',
    laterHint: 'Geht als Kommentar auf der Card an den Kunden, etwa 15 Minuten nach deiner letzten Datei.',
    saving: 'Wird gespeichert…',
    saved: 'Gespeichert. Sie geht mit der Lieferung raus.',
    tooLate: 'Zu spät: Diese Card ist schon beim Kunden. Die Notiz wurde nicht gesendet und es wurde nichts Neues gepostet.',
    closed: 'Diese Card ist schon beim Kunden. Eine Notiz kann mit der nächsten Version mitgehen.',
    sent: 'An den Kunden gesendet:',
    failed: 'Die Notiz konnte nicht gespeichert werden. Versuch es noch mal.',
    noRoute: 'Der Kunde dieser Card bekommt von hier keine Notizen. Deine Notiz wurde nicht gesendet.',
  },
}

export function useNoteCopy() {
  const [lang, setLang] = React.useState<'en' | 'de'>('en')
  React.useEffect(() => { if (/^de\b/i.test(navigator.language || '')) setLang('de') }, [])
  return NOTE_COPY[lang]
}

/** The field itself, shared with the /handin form where no request exists yet. */
export function NoteField({ id, value, onChange, onBlur, hint, disabled }: { id: string; value: string; onChange: (v: string) => void; onBlur?: () => void; hint: string; disabled?: boolean }) {
  const copy = useNoteCopy()
  return <div>
    <label htmlFor={id} className="text-sm font-medium text-text-primary">{copy.label}</label>
    <textarea id={id} data-delivery-note rows={2} maxLength={DELIVERY_NOTE_MAX} value={value} disabled={disabled} placeholder={copy.placeholder} onChange={e => onChange(e.target.value)} onBlur={onBlur} className="field mt-1.5 w-full resize-y py-2.5 text-sm" />
    <p className="mt-1.5 text-xs text-text-tertiary">{hint}</p>
  </div>
}

type Outcome = 'idle' | 'saving' | 'saved' | 'too_late' | 'failed' | 'no_route'

export function DeliveryNote({ token, draft, className = '' }: { token: string; draft?: string; className?: string }) {
  const copy = useNoteCopy()
  const { data: state, mutate } = useSWR<DeliveryNoteState>(`/r/${token}/note`, () => readDeliveryNote(token), { refreshInterval: 30000, revalidateOnFocus: true, shouldRetryOnError: false })
  const [value, setValue] = React.useState(draft || '')
  const [outcome, setOutcome] = React.useState<Outcome>('idle')
  const dirty = React.useRef(!!draft?.trim())
  const lastSent = React.useRef<string | null>(null)
  const timer = React.useRef<ReturnType<typeof setTimeout>>()

  const save = React.useCallback(async (text: string) => {
    clearTimeout(timer.current)
    dirty.current = false
    lastSent.current = text
    setOutcome('saving')
    try {
      const next = await saveDeliveryNote(token, text)
      await mutate(next, { revalidate: false })
      setOutcome(!next.available ? 'no_route' : next.status === 'too_late' ? 'too_late' : next.status === 'saved' || next.status === 'cleared' ? 'saved' : 'idle')
    } catch {
      dirty.current = true
      setOutcome('failed')
    }
  }, [token, mutate])

  // The note the card already holds, once, unless the editor is already typing.
  const seeded = React.useRef(false)
  React.useEffect(() => {
    if (!state || seeded.current) return
    seeded.current = true
    if (dirty.current) { if (state.available && state.reachable) void save(value); return }
    if (state.note) setValue(state.note)
  }, [state, save, value])

  React.useEffect(() => () => clearTimeout(timer.current), [])

  if (!state) return null
  if (!state.available) return outcome === 'no_route' || draft?.trim() ? <p role="status" className={`text-sm text-text-secondary ${className}`}>{copy.noRoute}</p> : null

  const sentBlock = state.sent_note ? <div className="mt-2 text-sm"><p className="text-xs text-text-tertiary">{copy.sent}</p><p className="mt-1 whitespace-pre-wrap break-words text-text-secondary">{state.sent_note}</p></div> : null

  if (!state.accepts && state.reachable) {
    return <section data-delivery-note-closed className={`rounded-xl border border-border bg-bg-secondary p-4 ${className}`}>
      <p role={outcome === 'too_late' ? 'alert' : 'status'} className={`text-sm ${outcome === 'too_late' ? 'text-status-error' : 'text-text-secondary'}`}>{outcome === 'too_late' ? copy.tooLate : copy.closed}</p>
      {outcome === 'too_late' && value.trim() && <p className="mt-2 whitespace-pre-wrap break-words text-sm text-text-tertiary">{value}</p>}
      {sentBlock}
    </section>
  }

  const onChange = (text: string) => {
    setValue(text)
    dirty.current = true
    if (outcome !== 'idle') setOutcome('idle')
    clearTimeout(timer.current)
    timer.current = setTimeout(() => void save(text), SAVE_AFTER_MS)
  }
  const onBlur = () => { if (dirty.current) void save(value) }

  return <section className={className}>
    <NoteField id={`note-${token}`} value={value} onChange={onChange} onBlur={onBlur} hint={state.window === 'later_version' ? copy.laterHint : copy.hint} />
    <p role="status" aria-live="polite" className={`mt-1 min-h-4 text-xs ${outcome === 'failed' ? 'text-status-error' : 'text-text-tertiary'}`}>{outcome === 'saving' ? copy.saving : outcome === 'saved' && value.trim() ? copy.saved : outcome === 'failed' || !state.reachable && dirty.current ? copy.failed : ''}</p>
    {sentBlock}
  </section>
}
