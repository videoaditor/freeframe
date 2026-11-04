import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react'
import { FlowView, type FlowViewProps } from '../flow-view'

const audio = new Blob(['a'])
const recorder = () => vi.fn().mockResolvedValue({ stop: vi.fn().mockResolvedValue(audio) })

function setup(over: Partial<FlowViewProps> = {}) {
  const props: FlowViewProps = {
    renderMedia: (overlay) => <div data-testid="media">{overlay}</div>,
    files: [{ id: 'a1', name: 'Hook 1' }, { id: 'a2', name: 'Hook 2' }],
    currentFileId: 'a1',
    onSelectFile: vi.fn(),
    getPlayhead: () => 3.2,
    onPause: vi.fn(),
    onSeek: vi.fn(),
    canComment: true,
    onSendNotes: vi.fn().mockResolvedValue(undefined),
    onApprove: vi.fn().mockResolvedValue(undefined),
    approved: false,
    dictate: vi.fn().mockResolvedValue('Hook too slow'),
    startRecording: recorder(),
    ...over,
  }
  render(<FlowView {...props} />)
  return props
}
afterEach(cleanup)

describe('FlowView', () => {
  it('shows the briefing files across the top and switches file', () => {
    const p = setup()
    expect(screen.getByRole('button', { name: 'Hook 1' })).toHaveAttribute('aria-current', 'true')
    fireEvent.click(screen.getByRole('button', { name: 'Hook 2' }))
    expect(p.onSelectFile).toHaveBeenCalledWith('a2')
  })

  it('Comment captures the playhead without pausing, records, then dictates into an editable note', async () => {
    const p = setup()
    fireEvent.click(screen.getByRole('button', { name: /comment/i }))
    expect(p.onPause).not.toHaveBeenCalled()
    expect(await screen.findByRole('button', { name: /stop/i })).toBeInTheDocument()
    expect(screen.getByText(/recording/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /stop/i }))
    const box = await screen.findByRole('textbox')
    expect(box).toHaveValue('Hook too slow')
    expect(p.dictate).toHaveBeenCalledWith(audio)
    fireEvent.change(box, { target: { value: 'Hook way too slow' } })
    expect(box).toHaveValue('Hook way too slow')
  })

  it('keeps the audio when dictation fails and Try again re-sends the same recording', async () => {
    const dictate = vi.fn().mockRejectedValueOnce({ detail: 'x' }).mockResolvedValueOnce('Second try')
    setup({ dictate })
    fireEvent.click(screen.getByRole('button', { name: /comment/i }))
    fireEvent.click(await screen.findByRole('button', { name: /stop/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not transcribe/i)
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))
    await waitFor(() => expect(screen.getByRole('textbox')).toHaveValue('Second try'))
    expect(dictate).toHaveBeenNthCalledWith(2, audio)
  })

  it('falls back to typing when the microphone is unavailable', async () => {
    setup({ startRecording: vi.fn().mockRejectedValue(new Error('denied')) })
    fireEvent.click(screen.getByRole('button', { name: /comment/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/microphone unavailable/i)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Typed note' } })
    expect(screen.getByRole('button', { name: /^send 1$/i })).toBeEnabled()
  })

  it('keeps the video playing while recording, pauses on the first stroke, and sends the ink with the note', async () => {
    const p = setup()
    fireEvent.click(screen.getByRole('button', { name: /comment/i }))
    expect(p.onPause).not.toHaveBeenCalled()
    await screen.findByRole('button', { name: /stop/i })
    const layer = screen.getByTestId('ink-layer')
    expect(layer).toHaveAttribute('data-on')
    layer.getBoundingClientRect = () => ({ left: 0, top: 0, width: 200, height: 400, right: 200, bottom: 400, x: 0, y: 0, toJSON: () => ({}) })
    fireEvent.pointerDown(layer, { clientX: 100, clientY: 200, pointerId: 1 })
    expect(p.onPause).toHaveBeenCalledTimes(1)
    fireEvent.pointerMove(layer, { clientX: 150, clientY: 300, pointerId: 1 })
    fireEvent.pointerUp(layer, { clientX: 150, clientY: 300, pointerId: 1 })
    fireEvent.click(screen.getByRole('button', { name: /stop/i }))
    await screen.findByRole('textbox')
    fireEvent.click(screen.getByRole('button', { name: /^send 1$/i }))
    await waitFor(() => expect(p.onSendNotes).toHaveBeenCalled())
    const sent = (p.onSendNotes as ReturnType<typeof vi.fn>).mock.calls[0][0][0]
    expect(sent.text).toBe('Hook too slow')
    expect(sent.annotation).toMatchObject({ format: 'ink.v1', marks: [{ k: 'stroke', t: 3.2 }] })
    expect(sent.annotation.marks[0].pts[0]).toEqual([0.5, 0.5])
    expect(typeof sent.annotation.mark_offset_ms).toBe('number')
  })

  it('the ink layer is inert when not recording', () => {
    setup()
    expect(screen.getByTestId('ink-layer')).not.toHaveAttribute('data-on')
  })

  it('keeps notes on screen when sending fails', async () => {
    setup({ onSendNotes: vi.fn().mockRejectedValue(new Error('x')) })
    fireEvent.click(screen.getByRole('button', { name: /comment/i }))
    fireEvent.click(await screen.findByRole('button', { name: /stop/i }))
    await screen.findByRole('textbox')
    fireEvent.click(screen.getByRole('button', { name: /^send 1$/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/notes are still here/i)
    expect(screen.getByRole('textbox')).toHaveValue('Hook too slow')
  })

  it('with no notes the right button is an explicit Approve', async () => {
    const p = setup()
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(p.onApprove).toHaveBeenCalled())
    expect(p.onSendNotes).not.toHaveBeenCalled()
  })

  it('hides the controls for view-only users', () => {
    setup({ canComment: false })
    expect(screen.queryByRole('button', { name: /comment/i })).not.toBeInTheDocument()
    expect(screen.getByText(/view-only/i)).toBeInTheDocument()
  })
})
