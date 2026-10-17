import { describe, expect, it, vi } from 'vitest'
import { renderHook } from '@testing-library/react'

// The bridge posts AutoReview comments without an SSE event (two-pass C1), so the asset page keeps a fresh
// version's comment list live with a bounded poll. SWR replaces the list wholesale - never a duplicate.
const swrCalls: { key: unknown; options: Record<string, unknown> }[] = []
vi.mock('swr', () => ({
  default: (key: unknown, _fetcher: unknown, options: Record<string, unknown>) => {
    swrCalls.push({ key, options })
    return { data: undefined, error: undefined, isLoading: false, mutate: vi.fn() }
  },
}))

import { commentPollMs, useComments } from '../use-comments'

const now = Date.parse('2026-10-17T12:00:00Z')

describe('commentPollMs', () => {
  it('polls every 5 s while the version is young enough for Guidance to still arrive', () => {
    expect(commentPollMs('2026-10-17T11:59:00+00:00', now)).toBe(5000)
    expect(commentPollMs('2026-10-17T11:50:30Z', now)).toBe(5000)
  })

  it('stops once the review has had its time, and for anything it cannot read', () => {
    expect(commentPollMs('2026-10-17T11:49:59Z', now)).toBe(0)
    expect(commentPollMs(undefined, now)).toBe(0)
    expect(commentPollMs('not a date', now)).toBe(0)
  })
})

describe('useComments', () => {
  it('hands SWR a refresh interval that re-checks the version age on every tick', () => {
    swrCalls.length = 0
    renderHook(() => useComments('a1', 'v1', new Date(Date.now() - 60_000).toISOString()))
    const interval = swrCalls.at(-1)!.options.refreshInterval as () => number
    expect(typeof interval).toBe('function')
    expect(interval()).toBe(5000)
  })

  it('does not poll without a version date (old callers)', () => {
    swrCalls.length = 0
    renderHook(() => useComments('a1', 'v1'))
    const interval = swrCalls.at(-1)!.options.refreshInterval as () => number
    expect(interval()).toBe(0)
  })
})
