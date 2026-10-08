import { expect, it } from 'vitest'
import { canSetUpAutoReview, needsAutoReviewSetup } from '../onboarding'
import type { User, Project } from '@/types'
import type { FileRequest } from '../platform'
const user = { id: 'customer', is_staff: false, preferences: {} } as User
const owned = { id: 'brand', role: 'owner' } as Project
it('starts new Whop and standalone customers, including customers without a brand', () => {
  expect(needsAutoReviewSetup(user, [], [])).toBe(true)
  expect(needsAutoReviewSetup(user, [owned], [])).toBe(true)
})
it('does not hijack editors, staff, existing requests or completed setup', () => {
  expect(canSetUpAutoReview(user, [{ role: 'editor' } as Project])).toBe(false)
  expect(needsAutoReviewSetup({ ...user, is_staff: true }, [], [])).toBe(false)
  expect(needsAutoReviewSetup(user, [owned], [{} as FileRequest])).toBe(false)
  expect(needsAutoReviewSetup({ ...user, preferences: { autoreview_setup: { version: 1, step: 'done' } } }, [], [])).toBe(false)
})
it('waits for actual user, project and request data, not an empty fallback', () => {
  expect(needsAutoReviewSetup(null, [], [])).toBe(false)
  expect(needsAutoReviewSetup(user, undefined, [])).toBe(false)
  expect(needsAutoReviewSetup(user, [], undefined)).toBe(false)
})
