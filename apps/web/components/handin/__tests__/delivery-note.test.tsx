import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act, cleanup } from '@testing-library/react'
import { SWRConfig } from 'swr'
import { DeliveryNote, NOTE_COPY } from '../delivery-note'

const read = vi.fn()
const save = vi.fn()
vi.mock('@/lib/platform', () => ({
  readDeliveryNote: (...a: unknown[]) => read(...a),
  saveDeliveryNote: (...a: unknown[]) => save(...a),
}))

const open = { available: true, reachable: true, accepts: true, status: 'open', window: 'until_delivery', note: null, sent_note: null, sent_at: null }
const mount = (props: { draft?: string } = {}) => render(<SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}><DeliveryNote token="tok" {...props} /></SWRConfig>)
const settle = () => act(async () => { await vi.advanceTimersByTimeAsync(0) })

beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: false }); read.mockReset(); save.mockReset() })
afterEach(() => { cleanup(); vi.useRealTimers() })

describe('the note to the client', () => {
  it('shows the field with its plain hint and the limit, prefilled with what the card holds', async () => {
    read.mockResolvedValue({ ...open, note: 'Two versions' })
    mount(); await settle()
    const box = screen.getByLabelText(NOTE_COPY.en.label) as HTMLTextAreaElement
    expect(box.value).toBe('Two versions')
    expect(box.maxLength).toBe(500)
    expect(screen.getByText(NOTE_COPY.en.hint)).toBeTruthy()
  })

  it('saves as the editor types and says it is saved', async () => {
    read.mockResolvedValue(open)
    save.mockResolvedValue({ ...open, status: 'saved', note: 'Hello' })
    mount(); await settle()
    fireEvent.change(screen.getByLabelText(NOTE_COPY.en.label), { target: { value: 'Hello' } })
    expect(save).not.toHaveBeenCalled()
    await act(async () => { await vi.advanceTimersByTimeAsync(1300) })
    expect(save).toHaveBeenCalledWith('tok', 'Hello')
    expect(screen.getByText(NOTE_COPY.en.saved)).toBeTruthy()
  })

  it('a note after the delivery: tells the editor it is too late and keeps their words on screen', async () => {
    read.mockResolvedValue(open)
    save.mockResolvedValue({ ...open, accepts: false, status: 'too_late', window: 'closed', sent_note: 'First note' })
    mount(); await settle()
    fireEvent.change(screen.getByLabelText(NOTE_COPY.en.label), { target: { value: 'Late words' } })
    await act(async () => { await vi.advanceTimersByTimeAsync(1300) })
    expect(screen.getByRole('alert').textContent).toBe(NOTE_COPY.en.tooLate)
    expect(screen.getByText('Late words')).toBeTruthy()
    expect(screen.getByText('First note')).toBeTruthy()
    expect(screen.queryByLabelText(NOTE_COPY.en.label)).toBeNull()
  })

  it('a card already with the client opens as closed, with what was said', async () => {
    read.mockResolvedValue({ ...open, accepts: false, status: 'too_late', window: 'closed', sent_note: 'First note' })
    mount(); await settle()
    expect(screen.getByText(NOTE_COPY.en.closed)).toBeTruthy()
    expect(screen.getByText('First note')).toBeTruthy()
    expect(screen.queryByLabelText(NOTE_COPY.en.label)).toBeNull()
  })

  it('a failed save says so and tries again on leaving the field', async () => {
    read.mockResolvedValue(open)
    save.mockRejectedValueOnce(new Error('503')).mockResolvedValue({ ...open, status: 'saved', note: 'x' })
    mount(); await settle()
    const box = screen.getByLabelText(NOTE_COPY.en.label)
    fireEvent.change(box, { target: { value: 'x' } })
    await act(async () => { await vi.advanceTimersByTimeAsync(1300) })
    expect(screen.getByText(NOTE_COPY.en.failed)).toBeTruthy()
    await act(async () => { fireEvent.blur(box); await vi.advanceTimersByTimeAsync(0) })
    expect(save).toHaveBeenCalledTimes(2)
    expect(screen.getByText(NOTE_COPY.en.saved)).toBeTruthy()
  })

  it('a request with no card shows nothing at all', async () => {
    read.mockResolvedValue({ ...open, available: false, accepts: false, status: 'unavailable' })
    const { container } = mount(); await settle()
    expect(container.textContent).toBe('')
  })

  it('a note typed on the /handin form is saved once the request exists; a client it cannot reach is said out loud', async () => {
    read.mockResolvedValue(open)
    save.mockResolvedValue({ ...open, status: 'saved', note: 'Draft' })
    mount({ draft: 'Draft' }); await settle(); await settle()
    expect(save).toHaveBeenCalledTimes(1)
    expect(save).toHaveBeenCalledWith('tok', 'Draft')
    cleanup(); read.mockResolvedValue({ ...open, available: false, accepts: false, status: 'unavailable' })
    mount({ draft: 'Draft' }); await settle()
    expect(screen.getByRole('status').textContent).toBe(NOTE_COPY.en.noRoute)
  })

  it('the German copy uses real umlauts', () => {
    const all = Object.values(NOTE_COPY.de).join(' ')
    expect(all).toContain('für')
    expect(all).toContain('ändern')
    expect(all).toContain('Zu spät')
    expect(all).not.toMatch(/fuer|aendern|spaet|naechste/)
  })
})
