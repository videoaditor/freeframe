/**
 * The editor has to be able to tell "the review is coming" from "nobody is looking".
 *
 * There is no reviewer ACCOUNT to ask about - it comments through a share link as a guest - so the
 * only trace is the guest email on its comments, the same list that badges them "Automated".
 */
import { describe, it, expect, beforeAll } from 'vitest'

const EMAIL = 'review@aditor.ai'
process.env.NEXT_PUBLIC_AUTOMATION_GUEST_EMAILS = EMAIL

// Imported inside beforeAll, not at the top: the module reads the setting ONCE at import, and a
// static import is hoisted above the assignment above - so the setting would not be there yet.
// (Also keeps this file off top-level await, which this tsconfig rejects.)
let summarise: typeof import('../review-status').summarise
let withinReviewWindow: typeof import('../review-status').withinReviewWindow
let reviewingIsPossible: typeof import('../review-status').reviewingIsPossible
let REVIEW_WINDOW_MS: number

beforeAll(async () => {
  const m = await import('../review-status')
  summarise = m.summarise
  withinReviewWindow = m.withinReviewWindow
  reviewingIsPossible = m.reviewingIsPossible
  REVIEW_WINDOW_MS = m.REVIEW_WINDOW_MS
})

const ours = (body: string) => ({ body, guest_author: { email: EMAIL } })
const theirs = (body: string) => ({ body, guest_author: { email: 'client@brand.com' } })

describe('reading whether the review has landed', () => {
  it('is still running while only other people have commented', () => {
    // A client note on the asset is not our review arriving.
    expect(summarise([theirs('Looks great!')]).state).toBe('running')
    expect(summarise([]).state).toBe('running')
  })

  it('counts must-fix apart from the rest, and never counts the summary', () => {
    const r = summarise([
      ours('Auto Review - 1 thing worth fixing, 2 smaller notes'),
      ours('Must fix - CTA missing. No call to action in the final 10 seconds.'),
      ours('No music bed. Voiceover only.'),
      ours('Hook execution. Punch in at 0:01.'),
      theirs('Client says hi'),
    ])
    expect(r).toEqual({ state: 'done', mustFix: 1, notes: 2 })
  })

  it('stops asking once the upload is old', () => {
    // A review takes about two minutes. Polling for ever because one failed is the worse bug.
    expect(withinReviewWindow(Date.now())).toBe(true)
    expect(withinReviewWindow(Date.now() - REVIEW_WINDOW_MS - 1000)).toBe(false)
    expect(withinReviewWindow('not a date')).toBe(false)
  })

  it('does nothing at all when no automation is configured', async () => {
    expect(reviewingIsPossible()).toBe(true)
    // The module reads the setting once at import, which is what keeps an unconfigured instance
    // from ever polling: no emails, no questions, no line on the row.
  })
})
