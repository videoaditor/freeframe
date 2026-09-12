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
import { api } from './api'

const AUTOMATION_EMAILS = new Set(
  (process.env.NEXT_PUBLIC_AUTOMATION_GUEST_EMAILS || '')
    .split(',')
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean)
)

export const REVIEW_POLL_MS = 20_000
/** Long enough for a slow read plus a cron tick; short enough that a dead review stops asking. */
export const REVIEW_WINDOW_MS = 15 * 60_000

export type ReviewState =
  | { state: 'off' }
  | { state: 'running' }
  | { state: 'done'; mustFix: number; notes: number }
  | { state: 'unknown' }

export function reviewingIsPossible(): boolean {
  return AUTOMATION_EMAILS.size > 0
}

/** Is this upload young enough that a review could still be on its way? */
export function withinReviewWindow(createdAt: number | string, now = Date.now()): boolean {
  const t = typeof createdAt === 'number' ? createdAt : Date.parse(createdAt)
  if (!Number.isFinite(t)) return false
  return now - t < REVIEW_WINDOW_MS
}

interface CommentLike {
  body?: string
  guest_author?: { email?: string } | null
}

/** MUST FIX leads the note, exactly as the reviewer writes it. Counting words rather than asking
 *  for a score, because there is no score: it was removed from everything an editor sees. */
export function summarise(comments: CommentLike[]): ReviewState {
  const ours = comments.filter((c) => {
    const email = (c.guest_author?.email || '').toLowerCase()
    return email && AUTOMATION_EMAILS.has(email)
  })
  if (!ours.length) return { state: 'running' }
  const isSummary = (b: string) => b.startsWith('Auto Review')
  const mustFix = ours.filter((c) => (c.body || '').startsWith('Must fix')).length
  const notes = ours.filter((c) => !isSummary(c.body || '') && !(c.body || '').startsWith('Must fix')).length
  return { state: 'done', mustFix, notes }
}

export async function fetchReviewState(assetId: string): Promise<ReviewState> {
  if (!reviewingIsPossible()) return { state: 'off' }
  try {
    const comments = await api.get<CommentLike[]>(`/assets/${assetId}/comments`)
    return summarise(comments || [])
  } catch {
    // A failed lookup is not "no review". Saying nothing beats saying the wrong thing.
    return { state: 'unknown' }
  }
}
