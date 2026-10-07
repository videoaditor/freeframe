import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import { ProductFeedback } from '../product-feedback'
import { api } from '@/lib/api'

const voice = vi.hoisted(() => ({
  start: vi.fn(), stop: vi.fn(), reset: vi.fn(), retry: vi.fn(), phase: 'idle', seconds: 0,
  busy: false, unsaved: false, recordingId: null as string | null, audioUrl: undefined as string | undefined,
  error: '', note: '', transcript: null as ((text: string) => void) | null,
}))
vi.mock('@/hooks/use-feedback-recording', () => ({ useFeedbackRecording: (callback: (text: string) => void) => { voice.transcript = callback; return voice } }))
vi.mock('@/lib/api', () => ({ api: { post: vi.fn() } }))
vi.mock('next/navigation', () => ({ usePathname: () => '/requests/123' }))
beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(voice, { busy: false, unsaved: false, recordingId: null, audioUrl: undefined, error: '', note: '', phase: 'idle' })
})

it('sends an audio-only report referencing its saved recording and resets only after receipt', async () => {
  voice.recordingId = 'saved-audio'
  voice.audioUrl = 'blob:audio'
  let resolve!: (data: unknown) => void
  vi.mocked(api.post).mockImplementation(() => new Promise(r => { resolve = r }))
  const user = userEvent.setup()
  render(<ProductFeedback />)
  await user.click(screen.getByRole('button', { name: 'Give feedback' }))
  await user.click(screen.getByRole('button', { name: 'Send feedback' }))
  expect(api.post).toHaveBeenCalledWith('/product-feedback', expect.objectContaining({ message: '', recording_id: 'saved-audio' }))
  expect(voice.reset).not.toHaveBeenCalled()
  await act(async () => resolve({ id: 'receipt', status: 'received' }))
  expect(voice.reset).toHaveBeenCalledOnce()
})

it.each([{ busy: true, unsaved: false }, { busy: false, unsaved: true }])('blocks submission until original audio is saved: %j', async state => {
  Object.assign(voice, state)
  const user = userEvent.setup()
  render(<ProductFeedback />)
  await user.click(screen.getByRole('button', { name: 'Give feedback' }))
  await user.type(screen.getByRole('textbox'), 'My feedback')
  expect(screen.getByRole('button', { name: 'Send feedback' })).toBeDisabled()
})

it('appends dictation without overwriting text typed while transcription was pending', async () => {
  const user = userEvent.setup()
  render(<ProductFeedback />)
  await user.click(screen.getByRole('button', { name: 'Give feedback' }))
  await user.type(screen.getByRole('textbox'), 'Keep this edit.')
  act(() => voice.transcript?.('And this idea.'))
  expect(screen.getByRole('textbox')).toHaveValue('Keep this edit.\n\nAnd this idea.')
  await user.click(screen.getByRole('button', { name: 'Close feedback' }))
  expect(voice.stop).toHaveBeenCalled()
})
