import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SWRConfig } from 'swr'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ToastProvider } from '@/components/shared/toast'
import { AutoreviewNav } from '../autoreview-nav'

const api = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/lib/api', () => ({ api }))
const assign = vi.fn()

beforeEach(() => {
  api.get.mockReset()
  assign.mockReset()
  Object.defineProperty(window, 'location', { configurable: true, value: { ...window.location, assign } })
})
afterEach(cleanup)

function mount(brands: { slug: string; name: string }[], collapsed = false) {
  api.get.mockImplementation(async (path: string) => {
    if (path === '/autoreview/brands') return { brands }
    if (path.startsWith('/autoreview/link?brand=')) return { url: `https://review.aditor.ai/brand/${path.split('=')[1]}?t=jwt` }
    throw new Error(path)
  })
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <ToastProvider><AutoreviewNav collapsed={collapsed} /></ToastProvider>
    </SWRConfig>,
  )
}

it('renders nothing without a linked brand', async () => {
  mount([])
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/autoreview/brands'))
  expect(screen.queryByRole('button', { name: 'AutoReview' })).toBeNull()
})

it('one brand: a click mints a fresh link and opens it in the same tab', async () => {
  mount([{ slug: 'audibene-gmbh', name: 'audibene-workspace' }])
  fireEvent.click(await screen.findByRole('button', { name: 'AutoReview' }))
  await waitFor(() => expect(assign).toHaveBeenCalledWith('https://review.aditor.ai/brand/audibene-gmbh?t=jwt'))
  expect(api.get).toHaveBeenCalledWith('/autoreview/link?brand=audibene-gmbh')
})

it('keeps its accessible name when the sidebar is collapsed', async () => {
  mount([{ slug: 'audibene-gmbh', name: 'audibene-workspace' }], true)
  expect(await screen.findByRole('button', { name: 'AutoReview' })).toBeVisible()
  expect(screen.queryByText('AutoReview')).toBeNull()
})

it('several brands: a small menu picks which one to open', async () => {
  mount([{ slug: 'audibene-gmbh', name: 'audibene-workspace' }, { slug: 'mynd-organics', name: 'Mynd' }])
  await userEvent.click(await screen.findByRole('button', { name: 'AutoReview' }))
  await userEvent.click(await screen.findByRole('menuitem', { name: 'Mynd' }))
  await waitFor(() => expect(assign).toHaveBeenCalledWith('https://review.aditor.ai/brand/mynd-organics?t=jwt'))
})

it('a failed link shows an error and does not navigate', async () => {
  mount([{ slug: 'audibene-gmbh', name: 'audibene-workspace' }])
  const button = await screen.findByRole('button', { name: 'AutoReview' })
  api.get.mockRejectedValueOnce(new Error('403'))
  fireEvent.click(button)
  expect(await screen.findByText("Couldn't open AutoReview. Try again.")).toBeVisible()
  expect(assign).not.toHaveBeenCalled()
})
