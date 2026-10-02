/**
 * Upload > Processing > Reviewing > Done.
 *
 * Saskia, 2026-10-02: an editor's V2 sat on "Processing" for hours and nobody could tell whether
 * the video or the review was stuck - the review's progress read as "processing" too. These pin
 * down every combination of what FreeFrame knows (the file) and what the review tool says (the
 * review), so a stuck video and a stuck review can never look alike again.
 */
import { describe, it, expect, beforeAll, vi, afterEach } from 'vitest'

process.env.NEXT_PUBLIC_REVIEW_GATE_URL = 'https://review.aditor.ai'

let m: typeof import('../stages')
beforeAll(async () => {
  m = await import('../stages')
})

const NOW = 1_800_000_000_000
const minutesAgo = (n: number) => NOW - n * 60_000
const states = (v: { steps: { key: string; state: string }[] }) => Object.fromEntries(v.steps.map((s) => [s.key, s.state]))

describe('while the file is still on its way', () => {
  it('uploading: only Upload is active, with its minutes', () => {
    const v = m.computeStages({ file: 'uploading', startedAt: minutesAgo(3), review: null, now: NOW })
    expect(states(v)).toEqual({ upload: 'active', processing: 'waiting', review: 'waiting', done: 'waiting' })
    expect(v.steps[0].minutes).toBe(3)
    expect(v.terminal).toBe(false)
    expect(v.problem).toBeUndefined()
  })

  it('processing: Upload is done, Processing is active and counts its minutes', () => {
    const v = m.computeStages({ file: 'processing', startedAt: minutesAgo(12), review: null, now: NOW })
    expect(states(v)).toEqual({ upload: 'done', processing: 'active', review: 'waiting', done: 'waiting' })
    expect(v.steps[1].minutes).toBe(12)
    expect(v.problem).toBeUndefined()
  })

  it('processing for 30+ minutes says it is taking longer than usual, and where to write', () => {
    const v = m.computeStages({ file: 'processing', startedAt: minutesAgo(m.PROCESSING_SLOW_MINUTES), review: null, now: NOW })
    expect(v.problem?.kind).toBe('slow')
    expect(v.problem?.message).toMatch(/taking longer than usual/)
    expect(v.problem?.message).toMatch(/Bug Catches/)
  })

  it('a processing failure is the editor-facing message, not a spinner', () => {
    const v = m.computeStages({ file: 'failed', startedAt: minutesAgo(70), review: null, now: NOW })
    expect(states(v).processing).toBe('failed')
    expect(v.terminal).toBe(true)
    expect(v.problem).toEqual({
      kind: 'failed',
      message: "This file failed to process. Try re-uploading it. If that doesn't work, write into Bug Catches.",
    })
  })
})

describe('once the file is ready, the review has its own stage', () => {
  const ready = (review: Parameters<typeof m.computeStages>[0]['review']) =>
    m.computeStages({ file: 'ready', startedAt: minutesAgo(20), review, now: NOW })

  it('waiting: Reviewing is active but says it has not started - not "processing"', () => {
    const v = ready({ stage: 'waiting' })
    expect(states(v)).toEqual({ upload: 'done', processing: 'done', review: 'active', done: 'waiting' })
    expect(v.steps[2].detail).toBe('Waiting to start')
  })

  it('reading: names the step and counts the review\'s own minutes, not the upload\'s', () => {
    const v = ready({ stage: 'reading', step: 'analysing', startedAgoSeconds: 240, quietSeconds: 20 })
    expect(states(v).review).toBe('active')
    expect(v.steps[2]).toMatchObject({ detail: 'Analysing', minutes: 4 })
    expect(v.problem).toBeUndefined()
  })

  it('reading for 15+ minutes is flagged slow', () => {
    const v = ready({ stage: 'reading', step: 'analysing', startedAgoSeconds: m.REVIEW_SLOW_MINUTES * 60, quietSeconds: 5 })
    expect(v.problem?.kind).toBe('slow')
  })

  it('reading with no progress for 10+ minutes is flagged even if it started recently', () => {
    const v = ready({ stage: 'reading', step: 'measuring', startedAgoSeconds: 12 * 60, quietSeconds: m.REVIEW_QUIET_MINUTES * 60 })
    expect(v.problem?.kind).toBe('slow')
  })

  it('a retry is shown as a retry, not as an error', () => {
    const v = ready({ stage: 'reading', retrying: true, startedAgoSeconds: 60, quietSeconds: 10 })
    expect(v.steps[2].detail).toBe('Retrying')
    expect(v.problem).toBeUndefined()
  })

  it.each([
    ['too-large', /too large for the review/],
    ['on-our-side', /problem on our side/],
    ['unreadable', /could not read this file/],
  ] as const)('a failed review (%s) says what happened and what to do', (failedKind, text) => {
    const v = ready({ stage: 'failed', failedKind })
    expect(states(v)).toMatchObject({ processing: 'done', review: 'failed' })
    expect(v.terminal).toBe(true)
    expect(v.problem?.kind).toBe('failed')
    expect(v.problem?.message).toMatch(text)
  })

  it('a deliberate skip is not a review that is still coming', () => {
    const v = ready({ stage: 'skipped' })
    expect(states(v)).toMatchObject({ review: 'skipped', done: 'skipped' })
    expect(v.terminal).toBe(true)
    expect(v.problem).toBeUndefined()
  })

  it('done and clean says so plainly - the answer a clean cut used to never get', () => {
    const v = ready({ stage: 'done', clean: true })
    expect(states(v)).toEqual({ upload: 'done', processing: 'done', review: 'done', done: 'done' })
    expect(v.steps[3].detail).toBe('Reviewed: nothing to fix')
    expect(v.headline).toBe('Reviewed: nothing to fix')
    expect(v.terminal).toBe(true)
  })

  it('done with notes points at them', () => {
    expect(ready({ stage: 'done', clean: false }).steps[3].detail).toBe('Reviewed: notes are ready')
  })
})

describe('a broken or missing review is never a review quietly running', () => {
  it('an unreachable review is "unknown", with its own words', () => {
    const v = m.computeStages({ file: 'ready', startedAt: minutesAgo(5), review: 'unreachable', now: NOW })
    expect(states(v).review).toBe('unknown')
    expect(v.steps[2].detail).toBe('Status unavailable')
    expect(v.terminal).toBe(false)
  })

  it('not asked yet is "checking", not "reviewing"', () => {
    const v = m.computeStages({ file: 'ready', startedAt: minutesAgo(5), review: null, now: NOW })
    expect(v.steps[2]).toMatchObject({ state: 'unknown', detail: 'Checking' })
  })

  it('a viewer who may not see the review sees Upload and Processing only', () => {
    for (const file of ['uploading', 'processing', 'ready', 'failed'] as const) {
      const v = m.computeStages({ file, startedAt: minutesAgo(2), review: 'off', now: NOW })
      expect(v.steps.map((s) => s.key)).toEqual(['upload', 'processing'])
    }
  })

  it('a screen that cannot tell the file state falls back on what the review says', () => {
    const v = m.computeStages({ file: 'unknown', review: { stage: 'reading', step: 'preparing', startedAgoSeconds: 30 }, now: NOW })
    expect(states(v).processing).toBe('done')
    const w = m.computeStages({ file: 'unknown', review: { stage: 'waiting' }, now: NOW })
    expect(states(w).processing).toBe('unknown')
  })
})

describe('a finished review of an EARLIER version is not a review of this one', () => {
  it('a newer version means the review is still waiting for it', () => {
    const v1Review = { stage: 'done', clean: true, reviewedVersion: 1 } as const
    expect(m.reconcileWithVersion(v1Review, 2)).toEqual({ stage: 'waiting' })
  })

  it('the same version keeps its answer', () => {
    const r = { stage: 'done', clean: true, reviewedVersion: 2 } as const
    expect(m.reconcileWithVersion(r, 2)).toBe(r)
  })

  it('only a finished review is overridden; everything else passes through', () => {
    expect(m.reconcileWithVersion('unreachable', 3)).toBe('unreachable')
    expect(m.reconcileWithVersion(null, 3)).toBeNull()
    const reading = { stage: 'reading', reviewedVersion: 1 } as const
    expect(m.reconcileWithVersion(reading, 2)).toBe(reading)
  })
})

describe('reading the review tool\'s answer', () => {
  it('parses the stage fields, ignoring anything it does not recognise', () => {
    expect(m.parseReviewStage({ state: 'pending', stage: 'reading', step: 'measuring', startedAgoSeconds: 90, quietSeconds: 4, attempts: 1, junk: 'x' }))
      .toMatchObject({ stage: 'reading', step: 'measuring', startedAgoSeconds: 90, quietSeconds: 4, attempts: 1 })
  })

  it('an older review tool sends no stage at all', () => {
    expect(m.parseReviewStage({ state: 'pending', note: 'The review will appear here.' })).toBeUndefined()
    expect(m.parseReviewStage(null)).toBeUndefined()
    expect(m.parseReviewStage({ stage: 'nonsense' })).toBeUndefined()
  })

  it('knows when an answer will not change, so polling can stop', () => {
    expect(m.isTerminalReview(undefined)).toBe(true)
    expect(m.isTerminalReview({ stage: 'done' })).toBe(true)
    expect(m.isTerminalReview({ stage: 'failed' })).toBe(true)
    expect(m.isTerminalReview({ stage: 'skipped' })).toBe(true)
    expect(m.isTerminalReview({ stage: 'reading' })).toBe(false)
    expect(m.isTerminalReview({ stage: 'waiting' })).toBe(false)
  })
})

describe('fetchReviewStage', () => {
  afterEach(() => vi.unstubAllGlobals())
  const answer = (body: unknown, ok = true) => vi.stubGlobal('fetch', vi.fn(async () => ({ ok, json: async () => body })))

  it('returns the stage when the review tool sends one', async () => {
    answer({ state: 'pending', stage: 'reading', step: 'analysing' })
    expect(await m.fetchReviewStage('a1')).toMatchObject({ stage: 'reading', step: 'analysing' })
  })

  it('a failed lookup is unreachable - NOT "pending", which would read as a review still running', async () => {
    answer({}, false)
    expect(await m.fetchReviewStage('a1')).toBe('unreachable')
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline') }))
    expect(await m.fetchReviewStage('a1')).toBe('unreachable')
  })

  it('an answer without a stage hides the review steps rather than guessing', async () => {
    answer({ state: 'pending', note: 'The review will appear here.' })
    expect(await m.fetchReviewStage('a1')).toBe('off')
  })
})
