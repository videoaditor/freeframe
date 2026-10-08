import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { SWRConfig } from 'swr'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { CustomerEntry } from '../customer-entry'
import { listRequests } from '@/lib/platform'
import { useAuthStore } from '@/stores/auth-store'
import type { User } from '@/types'
const { replace } = vi.hoisted(() => ({ replace: vi.fn() }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace }) }))
vi.mock('@/lib/platform', () => ({ listRequests: vi.fn() }))
beforeEach(() => {
  vi.resetAllMocks()
  useAuthStore.setState({ user: { id: 'new-owner', is_staff: false, preferences: {} } as User })
})
afterEach(cleanup)
function mount() { render(<SWRConfig value={{ provider: () => new Map(), shouldRetryOnError: false }}><CustomerEntry projects={[]}><p>Dashboard</p></CustomerEntry></SWRConfig>) }
it('takes a new signed-in owner straight to setup without showing an editor screen', async () => {
  vi.mocked(listRequests).mockResolvedValue([])
  mount()
  await waitFor(() => expect(replace).toHaveBeenCalledWith('/start'))
  expect(screen.queryByText('Dashboard')).not.toBeInTheDocument()
})
it('does not treat an unavailable request list as a new customer', async () => {
  vi.mocked(listRequests).mockRejectedValue(new Error('Unavailable'))
  mount()
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not open your workspace')
  expect(replace).not.toHaveBeenCalled()
})
it('opens the dashboard after a customer chooses to finish setup later', async () => {
  useAuthStore.setState({ user: { id: 'new-owner', is_staff: false, preferences: { autoreview_setup: { version: 1, step: 'done' } } } as unknown as User })
  vi.mocked(listRequests).mockResolvedValue([])
  mount()
  expect(await screen.findByText('Dashboard')).toBeInTheDocument()
  expect(replace).not.toHaveBeenCalled()
})
