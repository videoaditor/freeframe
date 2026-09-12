/**
 * Has the automation reviewed this upload yet?
 *
 * An editor who uploads and sees nothing cannot tell "the review is coming" from "nobody is
 * looking" (Saskia, 2026-09-12). A static sentence on the row cannot tell them either: it reads
 * the same on day one and day thirty. So the row asks.
 *
 * There is no account to ask about. The reviewer comments through a share link as a GUEST, so the
 * only trace it leaves is the guest email on its comments - the same list the review panel
 * already uses to badge those comments "Automated". No reviewer configured, no polling, no line.
 *
 * Bounded on purpose: it asks every POLL_MS for at most WINDOW_MS after the upload, and stops the
 * moment it finds something. A review takes about two minutes; a panel that polls for ever because
 * one review failed is a worse problem than a missing line.
 */
/**
 * ASKED OF THE REVIEWER, NOT OF THE COMMENTS.
 *
 * The first version inferred "the review has landed" from the presence of a comment by the
 * automation's guest email. That broke the moment a clean read stopped saying anything on the
 * timeline (Saskia, 2026-09-12: "say nothing on a timeline that is clean") - a clean video would
 * have shown "Review running" until the window closed, which is the exact confusion the line was
 * added to remove.
 *
 * The reviewer's own endpoint knows. It answers `ready` with two empty lists for a clean read,
 * which no amount of comment-counting can tell apart from "not started".
 */
const GATE_URL = (process.env.NEXT_PUBLIC_REVIEW_GATE_URL || '').replace(/\/$/, '')

export const REVIEW_POLL_MS = 20_000
/** Long enough for a slow read plus a cron tick; short enough that a dead review stops asking. */
export const REVIEW_WINDOW_MS = 15 * 60_000

export type ReviewState =
  | { state: 'off' }
  | { state: 'running' }
  | { state: 'done'; mustFix: number; notes: number }
  | { state: 'unknown' }

export function reviewingIsPossible(): boolean {
  return GATE_URL.length > 0
}

/** Is this upload young enough that a review could still be on its way? */
export function withinReviewWindow(createdAt: number | string, now = Date.now()): boolean {
  const t = typeof createdAt === 'number' ? createdAt : Date.parse(createdAt)
  if (!Number.isFinite(t)) return false
  return now - t < REVIEW_WINDOW_MS
}

interface GateReviewResponse {
  state?: 'ready' | 'pending'
  worthFixing?: string[]
  niceToHave?: string[]
}

/** No score anywhere: it was removed from everything an editor sees, so this counts findings. An
 *  empty pair of lists is a CLEAN read, which is a real answer and not a missing one. */
export function summarise(r: GateReviewResponse | null): ReviewState {
  if (!r || r.state !== 'ready') return { state: 'running' }
  return {
    state: 'done',
    mustFix: (r.worthFixing || []).length,
    notes: (r.niceToHave || []).length,
  }
}

export async function fetchReviewState(assetId: string): Promise<ReviewState> {
  if (!reviewingIsPossible()) return { state: 'off' }
  try {
    // The reviewer's own record, and deliberately not through `api`: this is a different origin
    // and needs no FreeFrame credentials - the asset id is the only thing it takes.
    const res = await fetch(`${GATE_URL}/api/gate/review?asset=${encodeURIComponent(assetId)}`)
    if (!res.ok) return { state: 'unknown' }
    return summarise((await res.json()) as GateReviewResponse)
  } catch {
    // A failed lookup is not "no review". Saying nothing beats saying the wrong thing.
    return { state: 'unknown' }
  }
}
