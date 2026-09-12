/**
 * The editor has to be able to tell "the review is coming" from "nobody is looking".
 *
 * There is no reviewer ACCOUNT to ask about - it comments through a share link as a guest - so the
 * only trace is the guest email on its comments, the same list that badges them "Automated".
 */
import { describe, it, expect, beforeAll } from 'vitest'

process.env.NEXT_PUBLIC_REVIEW_GATE_URL = 'https://review.aditor.ai'

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

describe('reading whether the review has landed', () => {
  it('is still running until the reviewer says ready', () => {
    expect(summarise(null).state).toBe('running')
    expect(summarise({ state: 'pending' }).state).toBe('running')
  })

  it('reads a CLEAN read as done, not as not-started', () => {
    // The whole reason this asks the reviewer instead of counting comments: from 2026-09-12 a
    // clean read says nothing on the timeline, so there is no comment to count. Two empty lists
    // is a real answer.
    expect(summarise({ state: 'ready', worthFixing: [], niceToHave: [] }))
      .toEqual({ state: 'done', mustFix: 0, notes: 0 })
  })

  it('counts must-fix apart from the rest', () => {
    expect(summarise({
      state: 'ready',
      worthFixing: ['Must fix - CTA missing.'],
      niceToHave: ['No music bed.', 'Hook execution. Punch in at 0:01.'],
    })).toEqual({ state: 'done', mustFix: 1, notes: 2 })
  })

  it('stops asking once the upload is old', () => {
    // A review takes about two minutes. Polling for ever because one failed is the worse bug.
    expect(withinReviewWindow(Date.now())).toBe(true)
    expect(withinReviewWindow(Date.now() - REVIEW_WINDOW_MS - 1000)).toBe(false)
    expect(withinReviewWindow('not a date')).toBe(false)
  })

  it('does nothing at all when no reviewer is configured', () => {
    // Empty gate URL = upstream's behaviour: no asking, no line on the row.
    expect(reviewingIsPossible()).toBe(true)
  })
})
