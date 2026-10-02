/**
 * Which stage a video is in: Upload, Processing, Reviewing, Done.
 *
 * Saskia, 2026-10-02: "we should make a distinction between uploading, processing and reviewing.
 * Right now it all reads as processing, so people don't know if the video got stuck or the review
 * got stuck." FreeFrame knows the first two (its own upload and transcode); the review tool
 * knows the third (GET /api/gate/review now carries a `stage`). This module joins the two into one
 * answer, and is pure on purpose: facts in, a description out, so every case is a plain test.
 *
 * Two rules it keeps:
 *  - A failed lookup is "unknown", never "reviewing". The old calm fallback hid a broken review
 *    behind a spinner, which is exactly the confusion this exists to remove.
 *  - Nothing here gates anything. It reports; the editor's link and the delivery are untouched.
 */

// Read here rather than imported from handin.ts, which imports this module for the stage types.
const GATE_BASE = process.env.NEXT_PUBLIC_REVIEW_GATE_URL ?? ''

export type StageKey = 'upload' | 'processing' | 'review' | 'done'
export type StageState = 'done' | 'active' | 'waiting' | 'failed' | 'unknown' | 'skipped'

/** After this long in one stage the editor is told it is taking longer than usual. */
export const PROCESSING_SLOW_MINUTES = 30
export const REVIEW_SLOW_MINUTES = 15
/** The review reported no progress at all for this long: quiet, so possibly stuck. */
export const REVIEW_QUIET_MINUTES = 10

/** What the review tool says about one file. Mirrors GET /api/gate/review (feedback-agent). */
export interface ReviewStageData {
  stage: 'waiting' | 'reading' | 'failed' | 'skipped' | 'done'
  step?: 'preparing' | 'measuring' | 'analysing' | 'finishing'
  startedAgoSeconds?: number
  quietSeconds?: number
  attempts?: number
  retrying?: boolean
  failedKind?: 'too-large' | 'on-our-side' | 'unreadable'
  clean?: boolean
  staleResults?: boolean
  /** The version number the review last finished reading, when it has finished one. */
  reviewedVersion?: number
}

/** 'off' = this build or this viewer does not see the review at all. 'unreachable' = asked, no answer. */
export type ReviewFacts = ReviewStageData | 'off' | 'unreachable' | null

export type FileFacts = 'uploading' | 'processing' | 'ready' | 'failed' | 'unknown'

export interface StageInput {
  file: FileFacts
  /** When the upload started, in ms. Minutes for Upload and Processing count from here. */
  startedAt?: number
  /** null = not asked yet. */
  review: ReviewFacts
  now: number
}

export interface StageStep {
  key: StageKey
  label: string
  state: StageState
  /** Short text next to the label, e.g. "Analysing". */
  detail?: string
  /** Whole minutes this step has been running, when known. */
  minutes?: number
}

export interface StageProblem {
  kind: 'slow' | 'failed'
  message: string
}

export interface StageView {
  steps: StageStep[]
  problem?: StageProblem
  /** One plain sentence for screen readers and for anything that wants a single line. */
  headline: string
  /** True once nothing is left to wait for (done, failed or skipped). Polling can stop. */
  terminal: boolean
}

export const BUG_CATCHES_NOTE = 'write into Bug Catches'

const STEP_LABEL: Record<NonNullable<ReviewStageData['step']>, string> = {
  preparing: 'Preparing',
  measuring: 'Measuring',
  analysing: 'Analysing',
  finishing: 'Finishing',
}

const FAILED_MESSAGE: Record<NonNullable<ReviewStageData['failedKind']>, string> = {
  'too-large': 'This file is too large for the review. Export a lighter version and upload it again.',
  'on-our-side': `The review could not run because of a problem on our side. If this stays, ${BUG_CATCHES_NOTE}.`,
  unreadable: `The review could not read this file. Try uploading it again. If that doesn't work, ${BUG_CATCHES_NOTE}.`,
}

export const PROCESSING_FAILED_MESSAGE = `This file failed to process. Try re-uploading it. If that doesn't work, ${BUG_CATCHES_NOTE}.`

function minutesBetween(from: number | undefined, now: number): number | undefined {
  if (from === undefined || !Number.isFinite(from)) return undefined
  return Math.max(0, Math.floor((now - from) / 60_000))
}

function step(key: StageKey, label: string, state: StageState, extra: Partial<StageStep> = {}): StageStep {
  return { key, label, state, ...extra }
}

/** Only the first parts of the pipeline - Upload and Processing - for a viewer who may not see the review. */
function withoutReview(steps: StageStep[]): StageStep[] {
  return steps.filter((s) => s.key === 'upload' || s.key === 'processing')
}

export function computeStages(input: StageInput): StageView {
  const { file, review, now } = input
  const elapsed = minutesBetween(input.startedAt, now)
  const reviewVisible = review !== 'off'

  const waitingReview = step('review', 'Reviewing', 'waiting')
  const waitingDone = step('done', 'Done', 'waiting')
  const finish = (steps: StageStep[], headline: string, terminal: boolean, problem?: StageProblem): StageView => ({
    steps: reviewVisible ? steps : withoutReview(steps),
    headline,
    terminal,
    ...(problem ? { problem } : {}),
  })

  if (file === 'uploading') {
    return finish(
      [step('upload', 'Upload', 'active', { minutes: elapsed }), step('processing', 'Processing', 'waiting'), waitingReview, waitingDone],
      'Uploading your video',
      false,
    )
  }

  if (file === 'failed') {
    return finish(
      [step('upload', 'Upload', 'done'), step('processing', 'Processing', 'failed'), waitingReview, waitingDone],
      'Processing failed',
      true,
      { kind: 'failed', message: PROCESSING_FAILED_MESSAGE },
    )
  }

  if (file === 'processing') {
    const slow = elapsed !== undefined && elapsed >= PROCESSING_SLOW_MINUTES
    return finish(
      [step('upload', 'Upload', 'done'), step('processing', 'Processing', 'active', { minutes: elapsed }), waitingReview, waitingDone],
      'Processing your video',
      false,
      slow ? { kind: 'slow', message: `Processing is taking longer than usual. If it does not finish soon, ${BUG_CATCHES_NOTE}.` } : undefined,
    )
  }

  // From here on the file is ready, or its state is unknown to this screen. The review's own answer
  // tells us how far things really are.
  const processingKnownDone =
    file === 'ready' || (typeof review === 'object' && review !== null && review.stage !== 'waiting')
  const upload = step('upload', 'Upload', 'done')
  const processing = step('processing', 'Processing', processingKnownDone ? 'done' : 'unknown')

  if (review === 'off') {
    return finish([upload, processing, waitingReview, waitingDone], 'Ready', true)
  }
  if (review === null) {
    return finish(
      [upload, processing, step('review', 'Reviewing', 'unknown', { detail: 'Checking' }), waitingDone],
      'Checking the review',
      false,
    )
  }
  if (review === 'unreachable') {
    return finish(
      [upload, processing, step('review', 'Reviewing', 'unknown', { detail: 'Status unavailable' }), waitingDone],
      'The review status is unavailable right now',
      false,
    )
  }

  switch (review.stage) {
    case 'waiting':
      return finish(
        [upload, processing, step('review', 'Reviewing', 'active', { detail: 'Waiting to start' }), waitingDone],
        'Waiting for the review to start',
        false,
      )
    case 'reading': {
      const minutes = review.startedAgoSeconds !== undefined ? Math.floor(review.startedAgoSeconds / 60) : undefined
      const quiet = review.quietSeconds !== undefined && review.quietSeconds >= REVIEW_QUIET_MINUTES * 60
      const slow = (minutes !== undefined && minutes >= REVIEW_SLOW_MINUTES) || quiet
      const detail = review.retrying ? 'Retrying' : review.step ? STEP_LABEL[review.step] : undefined
      return finish(
        [upload, processing, step('review', 'Reviewing', 'active', { detail, minutes }), waitingDone],
        'Reviewing your video',
        false,
        slow ? { kind: 'slow', message: `The review is taking longer than usual. If it does not finish soon, ${BUG_CATCHES_NOTE}.` } : undefined,
      )
    }
    case 'failed':
      return finish(
        [upload, processing, step('review', 'Reviewing', 'failed'), waitingDone],
        'The review could not finish',
        true,
        { kind: 'failed', message: FAILED_MESSAGE[review.failedKind ?? 'unreadable'] },
      )
    case 'skipped':
      return finish(
        [upload, processing, step('review', 'Reviewing', 'skipped', { detail: 'Not auto-reviewed' }), step('done', 'Done', 'skipped')],
        'This video was not auto-reviewed',
        true,
      )
    case 'done':
      return finish(
        [
          upload,
          processing,
          step('review', 'Reviewing', 'done'),
          step('done', 'Done', 'done', { detail: review.clean ? 'Reviewed: nothing to fix' : 'Reviewed: notes are ready' }),
        ],
        review.clean ? 'Reviewed: nothing to fix' : 'Reviewed: notes are ready',
        true,
      )
  }
}

/** Is this an answer that will not change, so polling can stop? */
export function isTerminalReview(r: ReviewStageData | undefined): boolean {
  // An older review tool sends no stage at all; its `ready` is final, as it always was.
  return r === undefined || r.stage === 'done' || r.stage === 'failed' || r.stage === 'skipped'
}

/** Pull the stage fields out of a gate response, if the review tool sent them. */
export function parseReviewStage(data: unknown): ReviewStageData | undefined {
  if (!data || typeof data !== 'object') return undefined
  const d = data as Record<string, unknown>
  const stage = d.stage
  if (stage !== 'waiting' && stage !== 'reading' && stage !== 'failed' && stage !== 'skipped' && stage !== 'done') return undefined
  const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : undefined)
  return {
    stage,
    ...(typeof d.step === 'string' ? { step: d.step as ReviewStageData['step'] } : {}),
    startedAgoSeconds: num(d.startedAgoSeconds),
    quietSeconds: num(d.quietSeconds),
    attempts: num(d.attempts),
    ...(d.retrying === true ? { retrying: true } : {}),
    ...(typeof d.failedKind === 'string' ? { failedKind: d.failedKind as ReviewStageData['failedKind'] } : {}),
    ...(typeof d.clean === 'boolean' ? { clean: d.clean } : {}),
    ...(d.staleResults === true ? { staleResults: true } : {}),
    reviewedVersion: num(d.version),
  }
}

/**
 * A finished review of an EARLIER version is not a review of this one.
 *
 * The review tool keeps one record per file. After a new version finishes processing, that record
 * still says "done" until the review picks the new version up, and the editor would be told
 * "Reviewed: nothing to fix" about a cut nobody has looked at. The review also reports which
 * version it last read, so a newer version means the review is still waiting for it.
 */
export function reconcileWithVersion(review: ReviewFacts, latestVersion: number | undefined): ReviewFacts {
  if (typeof review !== 'object' || review === null || review.stage !== 'done') return review
  if (latestVersion !== undefined && review.reviewedVersion !== undefined && review.reviewedVersion < latestVersion) {
    return { stage: 'waiting' }
  }
  return review
}

/**
 * Ask the review tool which stage this file is in.
 *
 * Distinct from `fetchReview`, which reports a failed lookup as "pending": here a failed lookup is
 * `'unreachable'`, so a broken review shows as unknown rather than as a review still running.
 */
export async function fetchReviewStage(assetId: string): Promise<ReviewStageData | 'off' | 'unreachable'> {
  if (GATE_BASE.trim().length === 0) return 'off'
  try {
    const res = await fetch(`${GATE_BASE.replace(/\/$/, '')}/api/gate/review?asset=${encodeURIComponent(assetId)}`)
    if (!res.ok) return 'unreachable'
    // A review tool that predates stages answers fine but carries none: the review steps are then
    // hidden rather than guessed at.
    return parseReviewStage(await res.json()) ?? 'off'
  } catch {
    return 'unreachable'
  }
}
