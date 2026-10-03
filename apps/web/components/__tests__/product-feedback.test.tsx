import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { ProductFeedback } from '../product-feedback'
import { api } from '@/lib/api'

vi.mock('@/lib/api', () => ({ api: { post: vi.fn() } }))
vi.mock('next/navigation', () => ({ usePathname: () => '/requests/123' }))

beforeEach(() => vi.clearAllMocks())

it('shows success only after persistence and sends no author or campaign claim', async () => {
  let resolve!: (value: unknown) => void
  vi.mocked(api.post).mockImplementation(() => new Promise(r => { resolve = r }))
  const user = userEvent.setup()
  render(<ProductFeedback />)
  await user.click(screen.getByRole('button', { name: 'Give feedback' }))
  await user.type(screen.getByLabelText('Your feedback'), 'The upload stopped.')
  await user.click(screen.getByRole('button', { name: 'Send feedback' }))
  expect(screen.queryByText('Feedback received')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Saving feedback…' })).toBeDisabled()
  const [path, body] = vi.mocked(api.post).mock.calls[0]
  expect(path).toBe('/product-feedback')
  expect(body).toEqual({ submission_id: expect.any(String), kind: 'bug', message: 'The upload stopped.', page_path: '/requests/123' })
  resolve({ id: 'receipt-123', status: 'received' })
  expect(await screen.findByText('Feedback received')).toBeInTheDocument()
  expect(screen.getByText('Receipt: receipt-123')).toBeInTheDocument()
})

it('retains message and submission ID after error for a safe retry', async () => {
  vi.mocked(api.post).mockRejectedValueOnce(new Error('timeout')).mockResolvedValueOnce({ id: 'receipt-123', status: 'received' })
  const user = userEvent.setup()
  render(<ProductFeedback />)
  await user.click(screen.getByRole('button', { name: 'Give feedback' }))
  await user.click(screen.getByLabelText('Suggest an improvement'))
  await user.type(screen.getByLabelText('Your feedback'), 'Let me sort reviews.')
  await user.click(screen.getByRole('button', { name: 'Send feedback' }))
  expect(await screen.findByRole('alert')).toHaveTextContent("We couldn't save your feedback")
  expect(screen.getByLabelText('Your feedback')).toHaveValue('Let me sort reviews.')
  await user.click(screen.getByRole('button', { name: 'Send feedback' }))
  expect(await screen.findByText('Feedback received')).toBeInTheDocument()
  expect(vi.mocked(api.post).mock.calls[1][1]).toEqual(vi.mocked(api.post).mock.calls[0][1])
})

it('returns focus to trigger on escape and preserves the draft', async () => {
  const user = userEvent.setup()
  render(<ProductFeedback />)
  const trigger = screen.getByRole('button', { name: 'Give feedback' })
  await user.click(trigger)
  await user.type(screen.getByLabelText('Your feedback'), 'Draft')
  await user.keyboard('{Escape}')
  await waitFor(() => expect(trigger).toHaveFocus())
  await user.click(trigger)
  expect(screen.getByLabelText('Your feedback')).toHaveValue('Draft')
})
