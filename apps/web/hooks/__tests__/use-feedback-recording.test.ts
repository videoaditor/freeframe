import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { api } from '@/lib/api'
import { useFeedbackRecording } from '../use-feedback-recording'

vi.mock('@/lib/api', () => ({ api: { upload: vi.fn(), post: vi.fn() } }))
let recorder: FakeRecorder
const stopTrack = vi.fn()
const stream = { getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream
class FakeRecorder {
  static isTypeSupported = () => true
  state = 'inactive'
  mimeType = 'audio/webm'
  ondataavailable?: (e: { data: Blob }) => void
  onstop?: () => void
  onerror?: () => void
  constructor() { recorder = this }
  start() { this.state = 'recording' }
  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['test audio'], { type: this.mimeType }) })
    this.onstop?.()
  }
}
beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('MediaRecorder', FakeRecorder)
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn().mockResolvedValue(stream) } })
  URL.createObjectURL = vi.fn(() => 'blob:recording')
  URL.revokeObjectURL = vi.fn()
  vi.mocked(api.upload).mockResolvedValue({ id: 'audio-1', status: 'saved' })
  vi.mocked(api.post).mockResolvedValue({ status: 'transcribed', text: 'Make uploads faster.' })
})
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

it('saves original audio before requesting a transcript', async () => {
  let resolve!: (v: unknown) => void
  vi.mocked(api.upload).mockImplementation(() => new Promise(r => { resolve = r }))
  const onTranscript = vi.fn()
  const { result } = renderHook(() => useFeedbackRecording(onTranscript))
  await act(async () => result.current.start())
  act(() => result.current.stop())
  expect(stopTrack).toHaveBeenCalled()
  expect(api.post).not.toHaveBeenCalled()
  expect(result.current.busy).toBe(true)
  await act(async () => resolve({ id: 'audio-1', status: 'saved' }))
  await waitFor(() => expect(onTranscript).toHaveBeenCalledWith('Make uploads faster.'))
  expect(api.post).toHaveBeenCalledWith('/product-feedback/recordings/audio-1/transcribe', {})
  expect(result.current.recordingId).toBe('audio-1')
})

it('retains original and upload ID after network failure, then retries safely', async () => {
  vi.mocked(api.upload).mockRejectedValueOnce(new Error('offline'))
  const { result } = renderHook(() => useFeedbackRecording(vi.fn()))
  await act(async () => result.current.start())
  act(() => result.current.stop())
  await waitFor(() => expect(result.current.error).toContain('not saved'))
  expect(result.current.unsaved).toBe(true)
  const first = vi.mocked(api.upload).mock.calls[0][1]
  await act(async () => result.current.retry())
  const second = vi.mocked(api.upload).mock.calls[1][1]
  expect(second.get('recording_id')).toBe(first.get('recording_id'))
  expect(result.current.recordingId).toBe('audio-1')
})

it('keeps the saved recording attachable when Wispr is unavailable', async () => {
  vi.mocked(api.post).mockResolvedValue({ status: 'unavailable', text: null })
  const onTranscript = vi.fn()
  const { result } = renderHook(() => useFeedbackRecording(onTranscript))
  await act(async () => result.current.start())
  act(() => result.current.stop())
  await waitFor(() => expect(result.current.recordingId).toBe('audio-1'))
  expect(result.current.note).toContain('Audio saved')
  expect(result.current.unsaved).toBe(false)
  expect(onTranscript).not.toHaveBeenCalled()
})

it('does not start listening if dismissed while permission is pending', async () => {
  let resolve!: (v: MediaStream) => void
  vi.mocked(navigator.mediaDevices.getUserMedia).mockImplementation(() => new Promise(r => { resolve = r }))
  const { result } = renderHook(() => useFeedbackRecording(vi.fn()))
  let pending!: Promise<void>
  act(() => { pending = result.current.start() })
  act(() => result.current.stop())
  await act(async () => { resolve(stream); await pending })
  expect(stopTrack).toHaveBeenCalled()
  expect(result.current.busy).toBe(false)
  expect(api.upload).not.toHaveBeenCalled()
})

it('shows a useful microphone-denied error and permits text feedback', async () => {
  vi.mocked(navigator.mediaDevices.getUserMedia).mockRejectedValue(new DOMException('denied', 'NotAllowedError'))
  const { result } = renderHook(() => useFeedbackRecording(vi.fn()))
  await act(async () => result.current.start())
  expect(result.current.error).toContain('Microphone')
  expect(result.current.busy).toBe(false)
  expect(result.current.unsaved).toBe(false)
})

it('stops microphone tracks when unmounted', async () => {
  const { result, unmount } = renderHook(() => useFeedbackRecording(vi.fn()))
  await act(async () => result.current.start())
  unmount()
  expect(stopTrack).toHaveBeenCalled()
  expect(recorder.state).toBe('inactive')
})


it('stops before the strict two-minute server limit and saves without manual action', async () => {
  vi.useFakeTimers()
  const { result } = renderHook(() => useFeedbackRecording(vi.fn()))
  await act(async () => result.current.start())
  await act(async () => vi.advanceTimersByTimeAsync(118000))
  expect(recorder.state).toBe('recording')
  await act(async () => vi.advanceTimersByTimeAsync(1000))
  expect(recorder.state).toBe('inactive')
  expect(stopTrack).toHaveBeenCalled()
  expect(result.current.recordingId).toBe('audio-1')
})
