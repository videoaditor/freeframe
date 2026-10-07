import { render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { CampaignBoundary } from '../campaign-boundary'

const state = vi.hoisted(() => ({ user: { suite_campaign: null as any }, data: undefined as any }))
vi.mock('@/stores/auth-store', () => ({ useAuthStore: () => state }))
vi.mock('swr', () => ({ default: () => ({ data: state.data }) }))
vi.mock('../product-feedback', () => ({ ProductFeedback: () => <button>Give feedback</button> }))
vi.mock('@/lib/api', () => ({ api: { get: vi.fn() } }))

beforeEach(() => { state.user.suite_campaign = null; state.data = undefined })
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

it('offers one feedback entry for customers without a trial campaign', () => {
  render(<CampaignBoundary><p>Tool content</p></CampaignBoundary>)
  expect(screen.getAllByRole('button', { name: 'Give feedback' })).toHaveLength(1)
})

it('offers one feedback entry for paid customers after their preview ends', () => {
  state.user.suite_campaign = { ...campaign, state: 'expired', previewOnly: false }
  render(<CampaignBoundary><p>Tool content</p></CampaignBoundary>)
  expect(screen.getAllByRole('button', { name: 'Give feedback' })).toHaveLength(1)
})
