import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { RequestWorkspace, SubmissionSuccess } from '../request-workspace'
import type { RequestAsset } from '@/lib/platform'
vi.mock('@/components/review/video-player', () => ({ VideoPlayer: ({ initialStreamUrl, comments }: { initialStreamUrl: string; comments: { author: { id: string; name: string } }[] }) => <div data-testid="player" data-author={comments?.[0]?.author.name} data-author-id={comments?.[0]?.author.id}>{initialStreamUrl}</div> }))
afterEach(cleanup)
it('keeps playback stable across signed URL rotations but switches on a new version', () => {
  const asset: RequestAsset = { asset_id: 'a', name: 'Cut', version: 1, version_id: 'v1', processing: 'ready', review_state: 'held', comments: [], media_url: 'https://media.test/cut.mp4?signature=one' }
  const props = { token: 't', onSelect: vi.fn(), onRefresh: vi.fn() }
  const { rerender } = render(<RequestWorkspace {...props} assets={[asset]} />)
  rerender(<RequestWorkspace {...props} assets={[{ ...asset, media_url: 'https://media.test/cut.mp4?signature=two' }]} />)
  expect(screen.getByTestId('player')).toHaveTextContent('signature=one')
  rerender(<RequestWorkspace {...props} assets={[{ ...asset, version: 2, version_id: 'v2', media_url: 'https://media.test/cut.mp4?signature=three' }]} />)
  expect(screen.getByTestId('player')).toHaveTextContent('signature=three')
})

it('keeps review activity compact and separate from the completion mascot', () => {
  render(<RequestWorkspace token="t" assets={[]} onSelect={vi.fn()} onRefresh={vi.fn()} />)
  expect(screen.getByText('Review in progress')).toBeVisible()
  expect(screen.queryByRole('img', { name: /robot|assistant/i })).toBeNull()
  expect(document.querySelector('.review-analysis')).not.toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Pause animation' }))
  expect(document.querySelector('.review-analysis')).toHaveAttribute('data-paused', 'true')
  expect(screen.getByText('Review in progress')).toBeVisible()
})

it('celebrates only the first completed visit and keeps a video completion cue', () => {
  localStorage.removeItem('request-celebrated:completion-test')
  const { unmount } = render(<SubmissionSuccess token="completion-test" brand="Northline" />)
  expect(document.querySelector('.request-confetti')).not.toBeNull()
  expect(screen.getByLabelText('Video submitted')).toBeVisible()
  unmount()
  render(<SubmissionSuccess token="completion-test" brand="Northline" />)
  expect(document.querySelector('.request-confetti')).toBeNull()
  expect(screen.getByText('Your ads were submitted')).toBeVisible()
})

it('shows a frozen source frame during review and only mounts playback after feedback is ready', () => {
  const asset: RequestAsset = { asset_id: 'a', name: 'Cut', version: 1, version_id: 'v1', processing: 'ready', review_state: 'reviewing', comments: [], media_url: '/cut.mp4' }
  const props = { token: 't', onSelect: vi.fn(), onRefresh: vi.fn() }
  const { rerender } = render(<RequestWorkspace {...props} assets={[asset]} />)
  expect(screen.queryByTestId('player')).toBeNull()
  const preview = document.querySelector('video')!
  expect(preview).toHaveAttribute('src', '/cut.mp4')
  expect(preview.controls).toBe(false)
  const pause = vi.spyOn(preview, 'pause').mockImplementation(() => {})
  fireEvent.play(preview)
  expect(pause).toHaveBeenCalled()
  rerender(<RequestWorkspace {...props} assets={[{ ...asset, review_state: 'held' }]} />)
  expect(screen.getByTestId('player')).toBeVisible()
  expect(document.querySelector('.review-analysis')).toBeNull()
})

it('uses the existing thumbnail without downloading video, and falls back if it fails', () => {
  render(<RequestWorkspace token="t" assets={[{ asset_id: 'a', name: 'Cut', version: 1, processing: 'ready', review_state: 'reviewing', comments: [], media_url: '/cut.mp4', thumbnail_url: '/cut.jpg' }]} onSelect={vi.fn()} onRefresh={vi.fn()} />)
  expect(screen.getByAltText('Still frame of your submitted video')).toHaveAttribute('src', '/cut.jpg')
  expect(document.querySelector('video')).toBeNull()
  fireEvent.error(screen.getByAltText('Still frame of your submitted video'))
  expect(document.querySelector('video')).toHaveAttribute('src', '/cut.mp4')
})


it('uses the request brand for comment and player attribution without changing the agent identity', () => {
  const asset: RequestAsset = { asset_id: 'a', name: 'Cut', version: 1, processing: 'ready', review_state: 'held', media_url: '/cut.mp4', comments: [{ t: 1, body: 'Hold the end card.' }] }
  const props = { token: 't', assets: [asset], onSelect: vi.fn(), onRefresh: vi.fn() }
  const { rerender } = render(<RequestWorkspace {...props} brand=" Northline " />)
  expect(screen.getByText('Northline')).toBeVisible()
  expect(screen.getByTestId('player')).toHaveAttribute('data-author', 'Northline')
  expect(screen.getByTestId('player')).toHaveAttribute('data-author-id', 'review-agent')
  rerender(<RequestWorkspace {...props} brand="  " />)
  expect(screen.getByText('Review team')).toBeVisible()
  expect(screen.getByTestId('player')).toHaveAttribute('data-author', 'Review team')
})



it('lets the editor replace a failed submitted version on the same asset', () => {
  const asset: RequestAsset = { asset_id: 'cut', name: 'Cut', version: 2, version_id: 'v2', processing: 'failed', review_state: 'unavailable', comments: [] }
  const revise = vi.fn()
  render(<RequestWorkspace token="failed-test" assets={[asset]} onSelect={vi.fn()} onRefresh={vi.fn()} onRevise={revise} />)
  expect(screen.getByText('Review unavailable')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Upload a replacement v3' }))
  expect(revise).toHaveBeenCalledWith(asset)
})
