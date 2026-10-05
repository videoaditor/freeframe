import { cleanup, render, screen } from '@testing-library/react'
import { SWRConfig } from 'swr'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import RequestPage from '../[token]/page'
import { viewRequest } from '@/lib/platform'
import { requestIterations, type IterationProgress } from '@/lib/iterations'
vi.mock('@/lib/platform', async original => ({ ...await original<typeof import('@/lib/platform')>(), viewRequest: vi.fn() }))
vi.mock('@/lib/iterations', async original => ({ ...await original<typeof import('@/lib/iterations')>(), requestIterations: vi.fn() }))
const parts: IterationProgress = { enabled: true, mode: 'components', simple: true, manifest: { schema_version: 1, summary: '', slots: [], recipes: [] }, slots: [], outputs: [], state: 'waiting', delivered: 0, total: 0, submitted: false, can_leave: false, editor_done: false }
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear()
  vi.mocked(viewRequest).mockResolvedValue({ title: 'ClearDay launch', brand: 'ClearDay', brief_excerpt: 'Use the approved hook and body.', review_share_token: 'share', expires_at: null, assets: [], receive_iterations: true })
  vi.mocked(requestIterations).mockResolvedValue(parts)
})
afterEach(cleanup)
function mount() { render(<SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}><RequestPage params={{ token: 'test' }} /></SWRConfig>) }
it('uses the confirmed parts format without giving the editor a mode switch', async () => {
  mount()
  expect(await screen.findByLabelText('Upload hooks')).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Complete ads' })).not.toBeInTheDocument()
  expect(screen.getByText('Use the approved hook and body.')).toBeVisible()
})
it('uses a stored complete-ad mode without exposing format configuration', async () => {
  vi.mocked(requestIterations).mockResolvedValue({ ...parts, mode: 'complete' })
  mount()
  expect(await screen.findByRole('button', { name: 'Drop your files to begin' })).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Separate parts' })).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Upload hooks')).not.toBeInTheDocument()
})
