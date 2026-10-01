import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import WhopPage from '../page'

const auth = vi.hoisted(() => ({ resetWhopEntry: vi.fn(), setTokens: vi.fn() }))
vi.mock('@/lib/auth', () => auth)
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks() })
it('clears previous identity and shows a recoverable error without accepting credentials', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: 'Open Review inside Whop.' }) }))
  render(<WhopPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Open Review inside Whop.')
  expect(auth.resetWhopEntry).toHaveBeenCalledOnce()
  expect(auth.setTokens).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
})
it('handles browser storage denial without hanging', async () => {
  auth.resetWhopEntry.mockImplementationOnce(() => { throw new Error('storage blocked') })
  render(<WhopPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent('browser storage')
  expect(auth.setTokens).not.toHaveBeenCalled()
})
