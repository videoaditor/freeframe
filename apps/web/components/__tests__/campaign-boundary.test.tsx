import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { CampaignBoundary } from '../campaign-boundary'

const state = vi.hoisted(() => ({ user: { id: 'demo-owner', suite_campaign: null as any }, data: undefined as any }))
vi.mock('@/stores/auth-store', () => ({ useAuthStore: () => state }))
vi.mock('swr', () => ({ default: () => ({ data: state.data }) }))
vi.mock('../product-feedback', () => ({ ProductFeedback: () => <button>Give feedback</button> }))
vi.mock('@/lib/api', () => ({ api: { get: vi.fn() } }))

beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(new Date('2026-10-07T00:00:00Z')); localStorage.clear(); state.user.id = 'demo-owner'; state.user.suite_campaign = null; state.data = undefined })
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks() })
const campaign = { id: 'telehealth_october_2026', tool: 'autoreview', endsAt: '2026-11-01T04:00:00Z', state: 'active', previewOnly: true }

it('keeps ordinary and paid users in the app', () => {
  state.user.suite_campaign = { ...campaign, state: 'expired', previewOnly: false }
  render(<CampaignBoundary><p>Tool content</p></CampaignBoundary>)
  expect(screen.getByText('Tool content')).toBeInTheDocument()
  expect(screen.queryByText('Your preview has ended')).not.toBeInTheDocument()
})

it('replaces expired tool content with both plan choices and feedback', () => {
  state.user.suite_campaign = { ...campaign, state: 'expired' }
  state.data = { reviewedAds: 20, recommendedPlan: 'team' }
  render(<CampaignBoundary><p>Tool content</p></CampaignBoundary>)
  expect(screen.queryByText('Tool content')).not.toBeInTheDocument()
  expect(screen.getByText('Your preview has ended')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Explore Team' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Explore Masterclass + Tools' })).toBeInTheDocument()
  expect(screen.getByText('Recommended for your usage: Team')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Give feedback' })).toBeInTheDocument()
})


it('remembers dismissal across remounts while preserving feedback and content', () => {
  state.user.suite_campaign = campaign
  const view = render(<CampaignBoundary><p>Tool content</p></CampaignBoundary>)
  fireEvent.click(screen.getByRole('button', { name: 'Dismiss preview notice' }))
  expect(screen.queryByText('Telehealth preview')).not.toBeInTheDocument()
  expect(screen.getByText('Tool content')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Give feedback' })).toBeInTheDocument()
  view.unmount()
  render(<CampaignBoundary><p>Tool content</p></CampaignBoundary>)
  expect(screen.queryByText('Telehealth preview')).not.toBeInTheDocument()
})

it('does not transfer dismissal to another account or campaign deadline', () => {
  state.user.suite_campaign = campaign
  const view = render(<CampaignBoundary><p>Tool content</p></CampaignBoundary>)
  fireEvent.click(screen.getByRole('button', { name: 'Dismiss preview notice' }))
  state.user.id = 'another-owner'
  view.rerender(<CampaignBoundary><p>Tool content</p></CampaignBoundary>)
  expect(screen.getByText('Telehealth preview')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Dismiss preview notice' }))
  state.user.suite_campaign = { ...campaign, endsAt: '2026-12-01T04:00:00Z' }
  view.rerender(<CampaignBoundary><p>Tool content</p></CampaignBoundary>)
  expect(screen.getByText('Telehealth preview')).toBeInTheDocument()
})

it('never dismisses the expired access gate', () => {
  state.user.suite_campaign = campaign
  const view = render(<CampaignBoundary><p>Tool content</p></CampaignBoundary>)
  fireEvent.click(screen.getByRole('button', { name: 'Dismiss preview notice' }))
  state.user.suite_campaign = { ...campaign, state: 'expired' }
  view.rerender(<CampaignBoundary><p>Tool content</p></CampaignBoundary>)
  expect(screen.getByText('Your preview has ended')).toBeInTheDocument()
  expect(screen.queryByText('Tool content')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Dismiss preview notice' })).not.toBeInTheDocument()
})

it('still dismisses for this visit when browser storage is unavailable', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
  state.user.suite_campaign = campaign
  render(<CampaignBoundary><p>Tool content</p></CampaignBoundary>)
  fireEvent.click(screen.getByRole('button', { name: 'Dismiss preview notice' }))
  expect(screen.queryByText('Telehealth preview')).not.toBeInTheDocument()
  expect(screen.getByText('Tool content')).toBeInTheDocument()
})
