import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SWRConfig } from 'swr'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AutoReviewSetup } from '../autoreview-setup'
import { api } from '@/lib/api'
import { createRequest, getRules, importRules, decideSuggestion, listRequests } from '@/lib/platform'
import { useAuthStore } from '@/stores/auth-store'
import type { User, Project } from '@/types'

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace }) }))
vi.mock('@/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }))
vi.mock('@/lib/platform', async original => ({ ...await original<typeof import('@/lib/platform')>(), createRequest: vi.fn(), getRules: vi.fn(), importRules: vi.fn(), decideSuggestion: vi.fn(), listRequests: vi.fn() }))
const brand = { id: 'brand1', name: 'Northline', created_by: 'customer', role: 'owner' } as Project
const request = { id: 'request1', project_id: brand.id, title: 'Summer launch', url: 'https://feedback.aditor.ai/r/test', state: 'live', assets: 0 } as Awaited<ReturnType<typeof createRequest>>
const user = { id: 'customer', is_staff: false, preferences: {}, is_superadmin: false } as User
beforeEach(() => {
  vi.resetAllMocks()
  useAuthStore.setState({ user })
  vi.mocked(api.get).mockResolvedValue([brand])
  vi.mocked(api.patch).mockImplementation(async (_path, body) => ({ ...user, preferences: body }))
  vi.mocked(getRules).mockResolvedValue({ brand: 'northline', rules: [], suggestions: [] })
  vi.mocked(listRequests).mockResolvedValue([])
  vi.mocked(createRequest).mockResolvedValue(request)
  vi.mocked(importRules).mockResolvedValue({ drafted: 1, found: 1 })
  vi.mocked(decideSuggestion).mockResolvedValue({ ok: true })
})
afterEach(() => { cleanup(); Reflect.deleteProperty(HTMLElement.prototype, 'scrollIntoView') })
async function mount() {
  const view = render(<SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0, shouldRetryOnError: false }}><AutoReviewSetup /></SWRConfig>)
  fireEvent.click(await screen.findByRole('button', { name: 'Get started' }))
  return view
}
it('skips the guide, creates a real briefing link and saves completion before the dashboard', async () => {
  await mount()
  fireEvent.click(await screen.findByRole('button', { name: 'Skip brand kit' }))
  fireEvent.change(await screen.findByRole('textbox', { name: 'Project name' }), { target: { value: 'Summer launch' } })
  fireEvent.click(screen.getByRole('button', { name: 'Paste text instead' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Briefing text or link' }), { target: { value: 'Keep the product visible.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create upload link' }))
  expect(await screen.findByRole('heading', { name: 'Your editor can take it from here.' })).toBeInTheDocument()
  expect(createRequest).toHaveBeenCalledWith(expect.objectContaining({ project_id: brand.id, brief_text: 'Keep the product visible.', receive_iterations: false, idempotency_key: expect.any(String) }))
  expect(importRules).not.toHaveBeenCalled()
  expect(screen.getByRole('link', { name: 'Upload an ad yourself' })).toHaveAttribute('href', request.url)
  fireEvent.click(screen.getByRole('button', { name: 'Open dashboard' }))
  await waitFor(() => expect(replace).toHaveBeenCalledWith('/home'))
  expect(api.patch).toHaveBeenLastCalledWith('/auth/me/preferences', { autoreview_setup: expect.objectContaining({ step: 'done', requestId: request.id }) })
})
it('never activates imported brand rules until the owner explicitly accepts', async () => {
  await mount()
  vi.mocked(getRules).mockResolvedValue({ brand: 'northline', rules: [], suggestions: [{ id: 'rule1', name: 'Logo', what: 'Show the logo at the end.' } as never] })
  fireEvent.change(screen.getByRole('textbox', { name: 'Brand guidelines' }), { target: { value: 'Show the logo at the end.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Read my brand kit' }))
  expect(await screen.findByText('Show the logo at the end.')).toBeInTheDocument()
  expect(decideSuggestion).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Use rule: Logo' }))
  await waitFor(() => expect(decideSuggestion).toHaveBeenCalledWith({ project_id: brand.id, suggestion_id: 'rule1', action: 'accept' }))
})
it('retains the briefing and idempotency key after an uncertain create response', async () => {
  await mount()
  fireEvent.click(screen.getByRole('button', { name: 'Skip brand kit' }))
  fireEvent.change(await screen.findByRole('textbox', { name: 'Project name' }), { target: { value: 'Summer launch' } })
  vi.mocked(createRequest).mockRejectedValueOnce(new Error('Connection interrupted. Try again.'))
  fireEvent.click(screen.getByRole('button', { name: 'Paste text instead' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Briefing text or link' }), { target: { value: 'Show the product.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create upload link' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Connection interrupted')
  const key = vi.mocked(createRequest).mock.calls[0][0].idempotency_key
  expect(screen.getByRole('textbox', { name: 'Project name' })).toHaveValue('Summer launch')
  fireEvent.click(screen.getByRole('button', { name: 'Create upload link' }))
  await waitFor(() => expect(createRequest).toHaveBeenCalledTimes(2))
  expect(vi.mocked(createRequest).mock.calls[1][0].idempotency_key).toBe(key)
})
it('shows a loading error rather than pretending an unavailable brand list is empty', async () => {
  vi.mocked(api.get).mockRejectedValue(new Error('Offline'))
  render(<SWRConfig value={{ provider: () => new Map(), shouldRetryOnError: false }}><AutoReviewSetup /></SWRConfig>)
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not load')
  expect(screen.queryByRole('textbox', { name: 'Brand name' })).not.toBeInTheDocument()
  expect(api.post).not.toHaveBeenCalled()
})
it('resumes the saved share link without creating another request', async () => {
  useAuthStore.setState({ user: { ...user, preferences: { autoreview_setup: { version: 1, step: 'share', projectId: brand.id, requestId: request.id } } } })
  vi.mocked(listRequests).mockResolvedValue([request])
  render(<SWRConfig value={{ provider: () => new Map(), shouldRetryOnError: false }}><AutoReviewSetup /></SWRConfig>)
  expect(await screen.findByRole('heading', { name: 'Your editor can take it from here.' })).toBeInTheDocument()
  expect(createRequest).not.toHaveBeenCalled()
})
it('recovers a brand created before a lost response without creating it twice', async () => {
  vi.mocked(api.get).mockResolvedValue([])
  await mount()
  fireEvent.change(screen.getByRole('textbox', { name: 'Brand name' }), { target: { value: 'Northline' } })
  vi.mocked(api.post).mockImplementationOnce(async () => {
    vi.mocked(api.get).mockResolvedValue([brand])
    throw new Error('Connection interrupted')
  })
  fireEvent.click(screen.getByRole('button', { name: 'Skip brand kit' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Connection interrupted')
  fireEvent.click(screen.getByRole('button', { name: 'Skip brand kit' }))
  expect(await screen.findByRole('textbox', { name: 'Project name' })).toBeInTheDocument()
  expect(api.post).toHaveBeenCalledTimes(1)
})
it('keeps the real link visible when storing setup progress fails after request creation', async () => {
  await mount()
  fireEvent.click(screen.getByRole('button', { name: 'Skip brand kit' }))
  fireEvent.change(await screen.findByRole('textbox', { name: 'Project name' }), { target: { value: 'Summer launch' } })
  fireEvent.click(screen.getByRole('button', { name: 'Paste text instead' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Briefing text or link' }), { target: { value: 'Show the product.' } })
  vi.mocked(api.patch).mockRejectedValueOnce(new Error('Could not save progress'))
  fireEvent.click(screen.getByRole('button', { name: 'Create upload link' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not save progress')
  expect(screen.getByRole('link', { name: 'Upload an ad yourself' })).toHaveAttribute('href', request.url)
  expect(createRequest).toHaveBeenCalledTimes(1)
})
it.each([{ available: [] }, { available: [brand] }])('recovers a deleted saved brand with available brands $available', async ({ available }) => {
  useAuthStore.setState({ user: { ...user, preferences: { autoreview_setup: { version: 1, step: 'brief', projectId: 'deleted-brand' } } } })
  vi.mocked(api.get).mockResolvedValue(available)
  vi.mocked(api.post).mockResolvedValue(brand)
  render(<SWRConfig value={{ provider: () => new Map(), shouldRetryOnError: false }}><AutoReviewSetup /></SWRConfig>)
  expect(await screen.findByText('Your previous brand is no longer available. Choose or create a brand to continue.')).toBeInTheDocument()
  if (!available.length) fireEvent.change(screen.getByRole('textbox', { name: 'Brand name' }), { target: { value: 'Northline' } })
  fireEvent.click(screen.getByRole('button', { name: 'Skip brand kit' }))
  expect(await screen.findByRole('textbox', { name: 'Project name' })).toBeInTheDocument()
  expect(api.patch).toHaveBeenLastCalledWith('/auth/me/preferences', { autoreview_setup: expect.objectContaining({ step: 'brief', projectId: brand.id }) })
})

it('uses the selected owned brand when continuing from the styled picker', async () => {
  const secondBrand = { ...brand, id: 'brand2', name: 'Second brand' }
  vi.mocked(api.get).mockResolvedValue([brand, secondBrand])
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() })
  await mount()
  fireEvent.keyDown(screen.getByRole('combobox', { name: 'Brand' }), { key: 'ArrowDown' })
  fireEvent.click(await screen.findByRole('option', { name: 'Second brand' }))
  fireEvent.click(screen.getByRole('button', { name: 'Skip brand kit' }))
  expect(await screen.findByRole('textbox', { name: 'Project name' })).toBeInTheDocument()
  expect(api.patch).toHaveBeenLastCalledWith('/auth/me/preferences', { autoreview_setup: expect.objectContaining({ projectId: secondBrand.id, step: 'brief' }) })
})
