'use client'

import * as React from 'react'
import { Check, Loader2, Mic, Pencil, RotateCcw, Send, Square, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { timecode } from '@/lib/platform'
import { dictate as dictateApi } from '@/lib/agents'
import { notesReducer, sendBlocked, sendable, type FlowNote } from '@/lib/flow-notes'
import { startMicRecording, type ActiveRecording, type StartRecording } from '@/lib/recorder'

export interface FlowFile { id: string; name: string; thumbnail_url?: string | null; version?: number | null }

export interface FlowViewProps {
  /** The existing media viewer (VideoPlayer + annotation overlay). Never cropped: it letterboxes. */
  media: React.ReactNode
  files: FlowFile[]
  currentFileId: string
  onSelectFile: (id: string) => void
  getPlayhead: () => number
  onPause: () => void
  onSeek: (t: number) => void
  drawing: boolean
  onToggleDrawing: () => void
  /** Drawing made on the frame; attached to the next note, then cleared. */
  annotation: Record<string, unknown> | null
  onAnnotationUsed: () => void
  canComment: boolean
  /** Posts every note as a comment. Rejects to keep the notes on screen. */
  onSendNotes: (notes: { text: string; t: number; annotation: Record<string, unknown> | null }[]) => Promise<void>
  onApprove: () => Promise<void> | void
  approved: boolean
  onExit?: () => void
  exitLabel?: string
  dictate?: (audio: Blob) => Promise<string>
  startRecording?: StartRecording
}

let seq = 0
const newId = () => `note-${Date.now()}-${seq++}`

function dictationMessage(e: unknown): string {
  const detail = (e as { detail?: string })?.detail
  return detail === 'dictation_unavailable' ? 'Dictation is not set up. Type your note instead.' : 'Could not transcribe. Try again or type it.'
}

export function FlowView(p: FlowViewProps) {
  const dictate = p.dictate ?? dictateApi
  const start = p.startRecording ?? startMicRecording
  const [notes, dispatch] = React.useReducer(notesReducer, [] as FlowNote[])
  const [active, setActive] = React.useState<{ id: string; rec: ActiveRecording; startedAt: number } | null>(null)
  const [elapsed, setElapsed] = React.useState(0)
  const [sending, setSending] = React.useState(false)
  const [error, setError] = React.useState('')
  const [messages, setMessages] = React.useState<Record<string, string>>({})

  React.useEffect(() => {
    if (!active) { setElapsed(0); return }
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - active.startedAt) / 1000)), 500)
    return () => clearInterval(id)
  }, [active])

  const transcribe = async (id: string, audio: Blob) => {
    dispatch({ type: 'transcribing', id, audio })
    setMessages(m => { const { [id]: _, ...rest } = m; return rest })
    try { dispatch({ type: 'done', id, text: await dictate(audio) }) }
    catch (e) { dispatch({ type: 'failed', id }); setMessages(m => ({ ...m, [id]: dictationMessage(e) })) }
  }

  const tapComment = async () => {
    setError('')
    if (active) {
      const { id, rec } = active
      setActive(null)
      await transcribe(id, await rec.stop())
      return
    }
    p.onPause()
    const id = newId()
    dispatch({ type: 'add', id, t: p.getPlayhead(), annotation: p.annotation })
    if (p.annotation) p.onAnnotationUsed()
    try { setActive({ id, rec: await start(), startedAt: Date.now() }) }
    catch {
      dispatch({ type: 'failed', id })
      setMessages(m => ({ ...m, [id]: 'Microphone unavailable. Type your note instead.' }))
    }
  }

  const ready = sendable(notes)
  const blocked = sendBlocked(notes)
  const send = async () => {
    setSending(true); setError('')
    try {
      if (!notes.length) { await p.onApprove(); return }
      await p.onSendNotes(ready.map(n => ({ text: n.text.trim(), t: n.t, annotation: n.annotation ?? null })))
      dispatch({ type: 'clear' })
    } catch { setError('Could not send. Your notes are still here. Try again.') }
    finally { setSending(false) }
  }

  const sendLabel = notes.length ? `Send ${ready.length || ''}`.trim() : p.approved ? 'Approved' : 'Approve'

  return (
    <div className="flex h-full min-h-0 flex-col bg-bg-primary" style={{ paddingTop: 'env(safe-area-inset-top)' }} data-testid="flow-view">
      {/* The briefing's files */}
      <div className="flex shrink-0 items-center gap-1 border-b border-border bg-bg-secondary pl-2">
        <nav aria-label="Files in this briefing" className="min-w-0 flex-1">
          <ul className="flex gap-1 overflow-x-auto py-1">
            {p.files.map(f => (
              <li key={f.id} className="shrink-0">
                <button type="button" onClick={() => f.id !== p.currentFileId && p.onSelectFile(f.id)} aria-current={f.id === p.currentFileId ? 'true' : undefined}
                  className={cn('press min-h-11 max-w-[160px] truncate rounded-full px-4 text-sm font-medium', f.id === p.currentFileId ? 'bg-bg-hover text-text-primary ring-1 ring-text-tertiary' : 'text-text-secondary hover:bg-bg-hover')}>
                  {f.name}
                </button>
              </li>
            ))}
          </ul>
        </nav>
        {p.onExit && <button type="button" onClick={p.onExit} className="press min-h-11 shrink-0 px-3 text-sm font-medium text-text-secondary hover:text-text-primary">{p.exitLabel ?? 'Exit'}</button>}
      </div>

      {/* 9:16 at full height, letterboxed never cropped */}
      <div className="flex min-h-0 flex-1 flex-col">{p.media}</div>

      {notes.length > 0 && (
        <ul aria-label="Your notes" className="max-h-[30dvh] shrink-0 space-y-2 overflow-y-auto border-t border-border bg-bg-secondary px-3 py-2">
          {notes.map(n => (
            <li key={n.id} className="flex items-start gap-2">
              <button type="button" onClick={() => p.onSeek(n.t)} aria-label={`Go to ${timecode(n.t)}`} className="press min-h-11 shrink-0 rounded-lg bg-bg-tertiary px-2.5 font-mono text-xs tabular-nums text-text-primary">{timecode(n.t)}</button>
              <div className="min-w-0 flex-1">
                {n.status === 'recording' && <p role="status" className="flex min-h-11 items-center text-sm text-text-secondary">Recording… tap Stop when you are done.</p>}
                {n.status === 'transcribing' && <p role="status" className="flex min-h-11 items-center gap-2 text-sm text-text-secondary"><Loader2 size={14} className="animate-spin motion-reduce:animate-none" />Transcribing…</p>}
                {(n.status === 'ready' || n.status === 'failed') && (
                  <>
                    <textarea aria-label={`Note at ${timecode(n.t)}`} value={n.text} rows={2} onChange={e => dispatch({ type: 'edit', id: n.id, text: e.target.value })}
                      className="w-full resize-none rounded-lg border border-border bg-bg-primary px-3 py-2 text-base text-text-primary outline-none focus:border-text-tertiary" />
                    {n.status === 'failed' && (
                      <p role="alert" className="flex flex-wrap items-center gap-x-3 text-xs text-text-secondary">
                        <span>{messages[n.id] ?? 'Could not transcribe.'}</span>
                        {n.audio && <button type="button" onClick={() => transcribe(n.id, n.audio!)} className="press inline-flex min-h-11 items-center gap-1 font-semibold text-text-primary"><RotateCcw size={12} />Try again</button>}
                      </p>
                    )}
                  </>
                )}
              </div>
              <button type="button" onClick={() => dispatch({ type: 'remove', id: n.id })} aria-label={`Delete note at ${timecode(n.t)}`} className="press grid h-11 w-11 shrink-0 place-items-center rounded-full text-text-secondary hover:bg-bg-hover"><X size={16} /></button>
            </li>
          ))}
        </ul>
      )}
      {error && <p role="alert" className="shrink-0 bg-bg-secondary px-4 py-2 text-sm text-status-error">{error}</p>}

      {/* One-hand bottom controls */}
      <div className="flex shrink-0 items-center gap-2 border-t border-border bg-bg-secondary px-3 pt-2" style={{ paddingBottom: 'max(0.5rem, env(safe-area-inset-bottom))' }}>
        {p.canComment ? (
          <>
            <button type="button" onClick={p.onToggleDrawing} aria-pressed={p.drawing} aria-label={p.drawing ? 'Finish drawing' : 'Draw on frame'}
              className={cn('press grid h-14 w-14 shrink-0 place-items-center rounded-full border border-border', p.drawing ? 'bg-bg-hover text-text-primary ring-1 ring-text-tertiary' : 'text-text-secondary hover:bg-bg-hover')}>
              {p.drawing ? <Check size={20} /> : <Pencil size={20} />}
            </button>
            <button type="button" onClick={tapComment}
              className="press inline-flex h-14 min-w-0 flex-1 items-center justify-center gap-2 rounded-full bg-accent px-5 text-base font-semibold text-text-inverse hover:bg-accent-hover">
              {active ? <><Square size={18} aria-hidden="true" />Stop · {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, '0')}</> : <><Mic size={20} aria-hidden="true" />Comment</>}
            </button>
            <button type="button" onClick={send} disabled={sending || blocked || (!notes.length && p.approved)}
              className="press inline-flex h-14 shrink-0 items-center justify-center gap-1.5 rounded-full border border-border px-4 text-sm font-semibold text-text-primary hover:bg-bg-hover disabled:opacity-50">
              {sending ? <Loader2 size={16} className="animate-spin motion-reduce:animate-none" /> : notes.length ? <Send size={16} aria-hidden="true" /> : <Check size={16} aria-hidden="true" />}{sendLabel}
            </button>
          </>
        ) : <p className="flex-1 py-3 text-center text-sm text-text-secondary">View-only access. Comments are disabled.</p>}
      </div>
    </div>
  )
}
