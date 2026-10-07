import { cleanup, fireEvent, render, screen } from '@testing-library/react'
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
  expect(screen.getByLabelText('Briefing preview')).toHaveTextContent('Use the approved hook and body.')
})
it('uses a stored complete-ad mode without exposing format configuration', async () => {
  vi.mocked(requestIterations).mockResolvedValue({ ...parts, mode: 'complete' })
  mount()
  expect(await screen.findByRole('button', { name: 'Drop your files to begin' })).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Separate parts' })).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Upload hooks')).not.toBeInTheDocument()
})

it('offers the actual full stored brief without presenting a text wall initially', async () => {
  const full = 'Use the approved hook and body. ' + 'Keep the pacing clear. '.repeat(30) + 'End with the approved ClearDay CTA.'
  vi.mocked(viewRequest).mockResolvedValue({ title: 'ClearDay launch', brand: 'ClearDay', brief_excerpt: full.slice(0, 500), brief_text: full, review_share_token: 'share', expires_at: null, assets: [], receive_iterations: true })
  mount()
  const disclosure = await screen.findByText('View full brief')
  const complete = screen.getByText(full)
  expect(complete).not.toBeVisible()
  fireEvent.click(disclosure)
  expect(complete).toBeVisible()
})
it('links to the actual external briefing when no full text was supplied', async () => {
  vi.mocked(viewRequest).mockResolvedValue({ title: 'ClearDay launch', brand: 'ClearDay', brief_excerpt: 'https://trello.com/c/approved', brief_url: 'https://trello.com/c/approved', review_share_token: 'share', expires_at: null, assets: [], receive_iterations: true })
  mount()
  expect(await screen.findByRole('link', { name: 'View full brief' })).toHaveAttribute('href', 'https://trello.com/c/approved')
})
it('does not label a legacy excerpt as the full briefing', async () => {
  mount()
  expect(await screen.findByText('View briefing preview')).toBeVisible()
  expect(screen.queryByText('View full brief')).not.toBeInTheDocument()
})
