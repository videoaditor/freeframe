import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SWRConfig } from 'swr'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import RequestPage from '../[token]/page'
import { finishRequest, requestReview, viewRequest, uploadToRequest, type RequestAsset } from '@/lib/platform'
vi.mock('@/lib/platform', async original => ({ ...await original<typeof import('@/lib/platform')>(), uploadToRequest: vi.fn(), finishRequest: vi.fn(), requestReview: vi.fn(), viewRequest: vi.fn() }))
vi.mock('@/components/review/video-player', () => ({ VideoPlayer: () => <div>Native player</div> }))
afterEach(() => { cleanup(); vi.useRealTimers() })
const asset: RequestAsset = { asset_id: 'cut', name: 'Cut.mp4', version: 2, version_id: 'v2', processing: 'ready', media_url: '/cut.mp4', comments: [], review_state: 'clear' }
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(viewRequest).mockResolvedValue({ title: 'Launch', brand: 'Northline', brief_excerpt: null, review_share_token: 'share', expires_at: null, assets: [{ id: 'cut', name: 'Cut.mp4' }] })
  vi.mocked(finishRequest).mockResolvedValue({ completed_at: '2026-09-28T06:00:00Z' })
})
function mount() { render(<SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}><RequestPage params={{ token: 'test' }} /></SWRConfig>) }
it('does not celebrate a clear legacy gate without exact-version review evidence', async () => {
  vi.mocked(requestReview).mockResolvedValue({ assets: [{ ...asset, review_state: 'unavailable' }], gate: { status: 'clear', open_must_fixes: 0 }, review_share_token: 'share' })
  mount()
  expect(await screen.findByText('Review unavailable')).toBeVisible()
  expect(finishRequest).not.toHaveBeenCalled()
  expect(screen.queryByText('Your ads were submitted')).not.toBeInTheDocument()
})
it('persists completion before celebrating and keeps the uploader absent on reopen', async () => {
  vi.mocked(requestReview).mockResolvedValue({ assets: [asset], gate: { status: 'clear', open_must_fixes: 0 }, review_share_token: 'share' })
  mount()
  expect(await screen.findByText('Your ads were submitted')).toBeVisible()
  expect(finishRequest).toHaveBeenCalledWith('test')
  cleanup()
  vi.mocked(finishRequest).mockClear()
  vi.mocked(viewRequest).mockResolvedValue({ title: 'Launch', brand: 'Northline', brief_excerpt: null, review_share_token: 'share', expires_at: null, assets: [{ id: 'cut', name: 'Cut.mp4' }], completed_at: '2026-09-28T06:00:00Z' })
  mount()
  expect(await screen.findByText('Your ads were submitted')).toBeVisible()
  expect(document.querySelector('input[type=file]')).toBeNull()
  expect(screen.getByText('Northline might reach out later, but consider your job done!')).toBeVisible()
  expect(screen.queryByRole('button', { name: /View final work|One more dance/ })).toBeNull()
  expect(screen.getByRole('img', { name: 'A proud robot celebrating your finished work' })).toHaveClass('review-robot-dance')
  fireEvent.click(screen.getByRole('button', { name: 'Pause animation' }))
  expect(screen.getByRole('img', { name: 'A proud robot celebrating your finished work' })).not.toHaveClass('review-robot-dance')
  expect(finishRequest).not.toHaveBeenCalled()
})
it('requires a deliberate revision action and retains the previous feedback', async () => {
  vi.mocked(requestReview).mockResolvedValue({ assets: [{ ...asset, version: 1, version_id: 'v1', review_state: 'held', comments: [{ id: 'fix', t: 2, body: 'Extend the end card', must_fix: true }] }], gate: { status: 'held', open_must_fixes: 1 }, review_share_token: 'share' })
  mount()
  fireEvent.click(await screen.findByRole('button', { name: 'Feedback done, back to upload v2' }))
  expect(screen.getByRole('button', { name: 'Drop Cut.mp4 · v2' })).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Back to v1 feedback' }))
  await waitFor(() => expect(screen.getByText('Extend the end card')).toBeVisible())
  expect(document.querySelector('input[type=file]')).toBeNull()
  expect(screen.queryByRole('button', { name: 'Reply' })).toBeNull()
  expect(screen.queryByTitle('Resolve')).toBeNull()
})

it('keeps retry visible when a later file in a submitted batch fails', async () => {
  vi.mocked(viewRequest).mockResolvedValue({ title: 'Launch', brand: 'Northline', brief_excerpt: null, review_share_token: 'share', expires_at: null, assets: [] })
  vi.mocked(requestReview).mockResolvedValue({ assets: [{ ...asset, review_state: 'held' }], gate: { status: 'held', open_must_fixes: 1 }, review_share_token: 'share' })
  vi.mocked(uploadToRequest).mockResolvedValueOnce({ asset_id: 'cut', version_number: 1 }).mockRejectedValueOnce(new Error('Connection lost'))
  mount()
  await screen.findByRole('button', { name: 'Drop your files to begin' })
  fireEvent.change(document.querySelector('input[type=file]')!, { target: { files: [new File(['a'], 'one.mp4'), new File(['b'], 'two.mp4')] } })
  expect(await screen.findByText('Connection lost')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Try again' })).toBeVisible()
})

it('keeps a long review below the shared 120 requests per ten minute limit', async () => {
  vi.useFakeTimers()
  vi.mocked(requestReview).mockResolvedValue({ assets: [{ ...asset, review_state: 'reviewing' }], gate: { status: 'reviewing', open_must_fixes: 0 }, review_share_token: 'share' })
  mount()
  await act(async () => { await vi.advanceTimersByTimeAsync(600000) })
  const total = vi.mocked(viewRequest).mock.calls.length + vi.mocked(requestReview).mock.calls.length
  expect(total).toBeGreaterThan(10)
  expect(total).toBeLessThan(100)
})

it('replaces a failed V2 on its own asset and completes only the reviewed V3', async () => {
  localStorage.setItem('aditor-request-who', JSON.stringify({name:'Test editor',email:'editor@example.test'}))
  vi.mocked(requestReview).mockResolvedValue({ assets: [{ ...asset, processing: 'failed', review_state: 'unavailable' }], gate: { status: 'unavailable', open_must_fixes: 0 }, review_share_token: 'share' })
  vi.mocked(uploadToRequest).mockImplementation(async () => {
    vi.mocked(requestReview).mockResolvedValue({ assets: [{ ...asset, version: 3, version_id: 'v3' }], gate: { status: 'clear', open_must_fixes: 0 }, review_share_token: 'share' })
    return { asset_id: 'cut', version_number: 3 }
  })
  mount()
  fireEvent.click(await screen.findByRole('button', { name: 'Upload a replacement v3' }))
  expect(finishRequest).not.toHaveBeenCalled()
  fireEvent.change(document.querySelector('input[type=file]')!, { target: { files: [new File(['corrected'], 'renamed-v3.mp4', {type:'video/mp4'})] } })
  expect(await screen.findByText('Your ads were submitted')).toBeVisible()
  expect(vi.mocked(uploadToRequest).mock.calls[0][4]?.assetId).toBe('cut')
  expect(finishRequest).toHaveBeenCalledTimes(1)
  localStorage.removeItem('aditor-request-who')
})
