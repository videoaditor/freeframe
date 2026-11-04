// Notes drafted in the phone "Flow" view before they are sent as comments.

export type NoteStatus = 'recording' | 'transcribing' | 'ready' | 'failed'
export interface FlowNote {
  id: string
  /** Playhead second captured when the note was started. */
  t: number
  text: string
  status: NoteStatus
  /** Kept when transcription fails so "Try again" never loses the recording. */
  audio?: Blob
  annotation?: Record<string, unknown> | null
}

export type NoteAction =
  | { type: 'add'; id: string; t: number; status?: NoteStatus; annotation?: Record<string, unknown> | null }
  | { type: 'transcribing'; id: string; audio: Blob }
  | { type: 'done'; id: string; text: string }
  | { type: 'failed'; id: string }
  | { type: 'edit'; id: string; text: string }
  | { type: 'remove'; id: string }
  | { type: 'clear' }

export function notesReducer(state: FlowNote[], a: NoteAction): FlowNote[] {
  switch (a.type) {
    case 'add':
      return [...state, { id: a.id, t: a.t, text: '', status: a.status ?? 'recording', annotation: a.annotation ?? null }].sort((x, y) => x.t - y.t)
    case 'transcribing':
      return state.map(n => (n.id === a.id ? { ...n, status: 'transcribing', audio: a.audio } : n))
    case 'done':
      return state.map(n => (n.id === a.id ? { ...n, status: 'ready', text: a.text, audio: undefined } : n))
    case 'failed':
      return state.map(n => (n.id === a.id ? { ...n, status: 'failed' } : n))
    case 'edit':
      // Typing over a failed transcription makes the note sendable without the audio.
      return state.map(n => (n.id === a.id ? { ...n, text: a.text, status: n.status === 'failed' && a.text.trim() ? 'ready' : n.status } : n))
    case 'remove':
      return state.filter(n => n.id !== a.id)
    case 'clear':
      return []
  }
}

export const sendable = (notes: FlowNote[]) => notes.filter(n => n.status === 'ready' && n.text.trim())
/** Send must wait while any note is still being recorded, transcribed or empty. */
export const sendBlocked = (notes: FlowNote[]) => notes.some(n => n.status === 'recording' || n.status === 'transcribing' || (n.status === 'failed' && !n.text.trim()) || (n.status === 'ready' && !n.text.trim()))
