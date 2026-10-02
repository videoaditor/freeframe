import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import type { AssetVersion } from '@/types'

// The video page's strip: where the NEWEST version is. These cover what the pure logic cannot -
// who may see it, when the review is asked at all, and which version a review answer is about.
const h = vi.hoisted(() => ({
  user: { is_staff: true } as { is_staff?: boolean } | null,
  configured: true,
  fetchReviewStage: vi.fn(),
}))

vi.mock('@/stores/auth-store', () => ({ useAuthStore: (sel: (s: { user: unknown }) => unknown) => sel({ user: h.user }) }))
vi.mock('@/lib/handin', () => ({ isHandinConfigured: () => h.configured }))
vi.mock('@/lib/stages', async (orig) => ({ ...(await orig<typeof import('@/lib/stages')>()), fetchReviewStage: h.fetchReviewStage }))

import { VersionStage } from '../version-stage'

const version = (n: number, status: AssetVersion['processing_status'], minutesOld: number): AssetVersion => ({
  id: `v${n}`, asset_id: 'a1', version_number: n, processing_status: status,
  created_by: 'u1', created_at: new Date(Date.now() - minutesOld * 60_000).toISOString(), deleted_at: null,
})

beforeEach(() => {
  h.user = { is_staff: true }
  h.configured = true
  h.fetchReviewStage.mockReset()
})

describe('the video page stage strip', () => {
  it('a version still processing shows Processing as the active step and does not ask the review yet', () => {
    render(<VersionStage assetId="a1" versions={[version(1, 'ready', 2000), version(2, 'processing', 12)]} />)
    expect(screen.getByTestId('stage-step-processing')).toHaveAttribute('data-state', 'active')
    expect(screen.getByTestId('stage-step-review')).toHaveAttribute('data-state', 'waiting')
    expect(h.fetchReviewStage).not.toHaveBeenCalled()
  })

  it('once ready it asks the review tool about THIS asset and shows the review as its own step', async () => {
    h.fetchReviewStage.mockResolvedValue({ stage: 'reading', step: 'analysing', startedAgoSeconds: 180, quietSeconds: 5 })
    render(<VersionStage assetId="a1" versions={[version(1, 'ready', 20)]} />)
    await waitFor(() => expect(screen.getByTestId('stage-step-review')).toHaveAttribute('data-state', 'active'))
    expect(screen.getByTestId('stage-step-processing')).toHaveAttribute('data-state', 'done')
    expect(screen.getByTestId('stage-step-review')).toHaveTextContent('Analysing')
    expect(h.fetchReviewStage).toHaveBeenCalledWith('a1')
  })

  it('a clean finished review says "Reviewed: nothing to fix"', async () => {
    h.fetchReviewStage.mockResolvedValue({ stage: 'done', clean: true, reviewedVersion: 1 })
    render(<VersionStage assetId="a1" versions={[version(1, 'ready', 20)]} />)
    await waitFor(() => expect(screen.getByTestId('stage-step-done')).toHaveTextContent('Reviewed: nothing to fix'))
  })

  it('a review of V1 is not shown as the review of a new V2', async () => {
    h.fetchReviewStage.mockResolvedValue({ stage: 'done', clean: true, reviewedVersion: 1 })
    render(<VersionStage assetId="a1" versions={[version(1, 'ready', 2000), version(2, 'ready', 5)]} />)
    await waitFor(() => expect(screen.getByTestId('stage-step-review')).toHaveAttribute('data-state', 'active'))
    expect(screen.getByTestId('stage-step-review')).toHaveTextContent('Waiting to start')
    expect(screen.queryByText(/nothing to fix/)).toBeNull()
  })

  it('an unreachable review shows as unavailable, not as a review running', async () => {
    h.fetchReviewStage.mockResolvedValue('unreachable')
    render(<VersionStage assetId="a1" versions={[version(1, 'ready', 20)]} />)
    await waitFor(() => expect(screen.getByTestId('stage-step-review')).toHaveAttribute('data-state', 'unknown'))
    expect(screen.getByTestId('stage-step-review')).toHaveTextContent('Status unavailable')
  })

  it('a customer never sees the review, and the review tool is never even asked', async () => {
    h.user = { is_staff: false }
    const { container } = render(<VersionStage assetId="a1" versions={[version(1, 'ready', 20)]} />)
    expect(container).toBeEmptyDOMElement()
    expect(h.fetchReviewStage).not.toHaveBeenCalled()
  })

  it('a customer still sees their own upload and processing, but no review steps', () => {
    h.user = { is_staff: false }
    render(<VersionStage assetId="a1" versions={[version(1, 'processing', 5)]} />)
    expect(screen.getByTestId('stage-step-processing')).toBeInTheDocument()
    expect(screen.queryByTestId('stage-step-review')).toBeNull()
  })

  it('a build with no review tool configured has no review steps and does not ask', () => {
    h.configured = false
    const { container } = render(<VersionStage assetId="a1" versions={[version(1, 'ready', 20)]} />)
    expect(container).toBeEmptyDOMElement()
    expect(h.fetchReviewStage).not.toHaveBeenCalled()
  })

  it('an old, uneventful finished strip stays out of the way', async () => {
    h.fetchReviewStage.mockResolvedValue({ stage: 'done', clean: true, reviewedVersion: 1 })
    const { container } = render(<VersionStage assetId="a1" versions={[version(1, 'ready', 60 * 24 * 3)]} />)
    await waitFor(() => expect(h.fetchReviewStage).toHaveBeenCalled())
    await waitFor(() => expect(container).toBeEmptyDOMElement())
  })

  it('but an old version with a problem still shows it', async () => {
    h.fetchReviewStage.mockResolvedValue({ stage: 'failed', failedKind: 'unreadable' })
    render(<VersionStage assetId="a1" versions={[version(1, 'ready', 60 * 24 * 3)]} />)
    await waitFor(() => expect(screen.getByTestId('stage-problem')).toHaveTextContent(/could not read this file/))
  })

  it('a version whose processing failed says so and where to write', () => {
    render(<VersionStage assetId="a1" versions={[version(1, 'failed', 90)]} />)
    expect(screen.getByRole('alert')).toHaveTextContent(/failed to process.*Bug Catches/)
  })

  it('renders nothing for a video with no versions', () => {
    const { container } = render(<VersionStage assetId="a1" versions={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
