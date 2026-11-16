'use client'

import * as React from 'react'
import { Check, Loader2, Mic, Pause, Play, Send, Square } from 'lucide-react'
import { timecode } from '@/lib/platform'

/** Hold longer than this and letting go ends the note; a quick tap latches it on until the next tap. */
export const HOLD_MS = 450

const videoIn = (root: React.RefObject<HTMLElement | null>) => root.current?.querySelector('video') ?? null

/** Drag to scrub. The track is 44px tall to touch, 4px to look at; ticks mark where notes were left. */
function Scrubber({ root, time, markers }: { root: React.RefObject<HTMLElement | null>; time: number; markers: number[] }) {
  const [duration, setDuration] = React.useState(0)
  const [drag, setDrag] = React.useState<number | null>(null)
  React.useEffect(() => {
    const el = root.current
    if (!el) return
    const sync = (e: Event) => { if (e.target instanceof HTMLVideoElement && Number.isFinite(e.target.duration)) setDuration(e.target.duration) }
    const events = ['loadedmetadata', 'durationchange'] as const
    events.forEach(ev => el.addEventListener(ev, sync, true))
    const v = videoIn(root)
    if (v && Number.isFinite(v.duration)) setDuration(v.duration)
    return () => events.forEach(ev => el.removeEventListener(ev, sync, true))
  }, [root])

  const frac = duration > 0 ? Math.min(1, Math.max(0, (drag ?? time / duration))) : 0
  const seekTo = (e: React.PointerEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    const f = r.width > 0 ? Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) : 0
    setDrag(f)
    const v = videoIn(root)
    if (v && duration > 0) v.currentTime = f * duration
  }
  const step = (e: React.KeyboardEvent) => {
    const d = e.key === 'ArrowRight' ? 5 : e.key === 'ArrowLeft' ? -5 : 0
    const v = videoIn(root)
    if (!d || !v) return
    e.preventDefault()
    v.currentTime = Math.min(duration, Math.max(0, v.currentTime + d))
  }

  return (
    <>
      <span className="ep-time" aria-hidden="true">{timecode(drag !== null ? drag * duration : time)}</span>
      <div
        className="ep-track" role="slider" tabIndex={0} aria-label="Seek" aria-valuemin={0} aria-valuemax={Math.round(duration)} aria-valuenow={Math.round(frac * duration)} aria-valuetext={`${timecode(frac * duration)} of ${timecode(duration)}`}
        onPointerDown={e => { if (e.pointerType === 'mouse' && e.button !== 0) return; try { e.currentTarget.setPointerCapture(e.pointerId) } catch { /* pointer already gone */ } seekTo(e) }}
        onPointerMove={e => { if (drag !== null) seekTo(e) }}
        onPointerUp={() => setDrag(null)} onPointerCancel={() => setDrag(null)} onKeyDown={step}
      >
        <span className="ep-rail" />
        <span className="ep-fill" style={{ width: `${frac * 100}%` }} />
        {duration > 0 && markers.map((t, i) => <span key={i} className="ep-tick" style={{ left: `${Math.min(100, (t / duration) * 100)}%` }} />)}
        <span className="ep-knob" style={{ left: `${frac * 100}%` }} />
      </div>
      <span className="ep-time" aria-hidden="true">{timecode(duration)}</span>
    </>
  )
}

export interface EmbedControlsProps {
  /** The flow view's root: the <video> inside it is what plays and scrubs. */
  root: React.RefObject<HTMLElement | null>
  playing: boolean
  time: number
  /** Where notes were left, in seconds. */
  markers: number[]
  canComment: boolean
  recording: boolean
  elapsed: number
  /** Start / stop the existing voice-and-ink note (the flow view's own logic). */
  onRecordStart: () => void | Promise<void>
  onRecordStop: () => void | Promise<void>
  onCancel: () => void
  /** Notes in flight: "Transcribing…", "2 notes saved". */
  status: string | null
  finish: { label: string; hasNotes: boolean; busy: boolean; disabled: boolean; onClick: () => void }
  /** Stepper for a folder share, under the top edge. */
  nav?: React.ReactNode
  /** Errors, retries and the Approved toast, stacked under the top edge. */
  children?: React.ReactNode
}

/**
 * Review Player v1 for the share page's ?embed=1: playback first. The video fills the frame; one panel sits on its bottom edge
 * with the scrub bar, play/pause, "hold to comment" and the Send / Approve action. Everything sizes by the tile, not the viewport.
 */
export function EmbedControls(p: EmbedControlsProps) {
  const play = () => { const v = videoIn(p.root); if (!v) return; if (v.paused) v.play().catch(() => {}); else v.pause() }
  const label = timecode(p.time)
  const clock = `${Math.floor(p.elapsed / 60)}:${String(p.elapsed % 60).padStart(2, '0')}`

  // Press-and-hold records while held; a quick tap latches (needed for a mouse, which can't hold and draw), the next tap ends it.
  const downAt = React.useRef(0)
  const ignoreUp = React.useRef(false)
  const stopWhenLive = React.useRef(false)
  const [latched, setLatched] = React.useState(false)
  const recordingRef = React.useRef(p.recording)
  recordingRef.current = p.recording
  // Playback goes on after a note: drawing pauses the picture, so pick it up again if it was running when the note began.
  const wasPlaying = React.useRef(false)
  const playingRef = React.useRef(p.playing)
  playingRef.current = p.playing
  React.useEffect(() => {
    if (p.recording) { wasPlaying.current = wasPlaying.current || playingRef.current; return }
    if (wasPlaying.current) { wasPlaying.current = false; const v = videoIn(p.root); if (v?.paused && !v.ended) v.play().catch(() => {}) }
  }, [p.recording]) // eslint-disable-line react-hooks/exhaustive-deps
  React.useEffect(() => {
    if (!p.recording) { setLatched(false); return }
    if (stopWhenLive.current) { stopWhenLive.current = false; void p.onRecordStop() }
  }, [p.recording]) // eslint-disable-line react-hooks/exhaustive-deps
  const down = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (e.pointerType === 'mouse' && e.button !== 0) return
    try { e.currentTarget.setPointerCapture(e.pointerId) } catch { /* pointer already gone */ }
    if (recordingRef.current) { ignoreUp.current = true; void p.onRecordStop(); return }
    ignoreUp.current = false
    wasPlaying.current = playingRef.current
    downAt.current = Date.now()
    void p.onRecordStart()
  }
  const up = () => {
    if (ignoreUp.current) { ignoreUp.current = false; return }
    if (Date.now() - downAt.current < HOLD_MS) { setLatched(true); return }
    if (recordingRef.current) void p.onRecordStop(); else stopWhenLive.current = true
  }
  const keyboard = (e: React.MouseEvent) => { if (e.detail !== 0) return; if (recordingRef.current) void p.onRecordStop(); else { wasPlaying.current = playingRef.current; void p.onRecordStart() } }

  // Long text for wide tiles, a short one for narrow tiles (CSS picks by the tile's width).
  const holdLabel = p.recording
    ? (latched ? [`Tap to stop · ${clock}`, `Stop · ${clock}`] : [`Release to send · ${clock}`, `Release · ${clock}`])
    : null

  return (
    <div className="ep" data-testid="embed-controls" data-recording={p.recording ? '' : undefined}>
      <div className="ep-top">
        {p.recording ? (
          <div className="ep-rec" role="status" aria-label="Recording">
            <span className="ep-dot" aria-hidden="true" />
            <span data-testid="rec-timer" className="font-mono tabular-nums">{clock}</span>
            <span className="ep-hint">Draw on the video while you talk</span>
            <button type="button" onClick={p.onCancel} aria-label="Cancel recording" className="ep-cancel">Cancel</button>
          </div>
        ) : p.nav}
        {p.status && !p.recording && <p role="status" className="ep-status">{p.status.endsWith('…') ? <Loader2 size={14} className="animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <Check size={14} aria-hidden="true" />}{p.status}</p>}
        {p.children}
      </div>

      {!p.playing && !p.recording && (
        <button type="button" onClick={play} aria-label="Play" className="ep-bigplay"><Play size={26} fill="currentColor" aria-hidden="true" /></button>
      )}

      <div className="ep-panel">
        <button type="button" onClick={play} aria-label={p.playing ? 'Pause' : 'Play'} className="ep-btn ep-play">
          {p.playing ? <Pause size={20} fill="currentColor" aria-hidden="true" /> : <Play size={20} fill="currentColor" aria-hidden="true" />}
        </button>
        <div className="ep-scrub"><Scrubber root={p.root} time={p.time} markers={p.markers} /></div>
        {p.canComment && (
          <button type="button" aria-label={p.recording ? 'Stop recording' : `Comment at ${label}`} aria-pressed={p.recording}
            onPointerDown={down} onPointerUp={up} onPointerCancel={up} onClick={keyboard} onContextMenu={e => e.preventDefault()}
            className="ep-hold">
            {p.recording ? <Square size={16} fill="currentColor" aria-hidden="true" /> : <Mic size={18} aria-hidden="true" />}
            {holdLabel
              ? <><span className="ep-wide">{holdLabel[0]}</span><span className="ep-short">{holdLabel[1]}</span></>
              : <><span className="ep-long">Hold to comment at {label}</span><span className="ep-mid">Hold to talk · {label}</span><span className="ep-short">Hold · {label}</span></>}
          </button>
        )}
        <button type="button" onClick={p.finish.onClick} disabled={p.finish.disabled} aria-label={p.finish.label} className="ep-btn ep-finish">
          {p.finish.busy ? <Loader2 size={18} className="animate-spin motion-reduce:animate-none" aria-hidden="true" /> : p.finish.hasNotes ? <Send size={18} aria-hidden="true" /> : <Check size={18} aria-hidden="true" />}
          <span className="ep-lbl">{p.finish.label}</span>
        </button>
      </div>
    </div>
  )
}
