'use client'

import * as React from 'react'
import { useAuthStore } from '@/stores/auth-store'
import { StageStrip } from '@/components/review/stage-strip'
import { isHandinConfigured } from '@/lib/handin'
import { REVIEW_POLL_MS } from '@/lib/review-status'
import {
  computeStages,
  fetchReviewStage,
  reconcileWithVersion,
  type FileFacts,
  type ReviewFacts,
} from '@/lib/stages'
import type { AssetVersion } from '@/types'

/** A finished, uneventful strip is only worth showing while the result is fresh. */
const FRESH_MS = 6 * 60 * 60_000
/** Redraw the minutes without asking anyone anything. */
const TICK_MS = 30_000

function fileFacts(status: AssetVersion['processing_status'] | undefined): FileFacts {
  return status ?? 'unknown'
}

/**
 * The strip under the video page's header: where the NEWEST version of this video is right now.
 *
 * Saskia, 2026-10-02: an editor's V2 sat on "Processing" and nobody could tell whether the video
 * or the review was stuck. FreeFrame's own status says nothing about the review, so this asks the
 * review tool as well - but only once the file has finished processing, and never for a customer,
 * who must not see the automation's status at all (its comments are hidden from them too).
 */
export function VersionStage({ assetId, versions }: { assetId: string; versions: AssetVersion[] }) {
  const user = useAuthStore((s) => s.user)
  // Only an explicit `false` hides it: open-source installs have no is_staff at all. And a build
  // with no review tool configured has no review steps to show to anyone.
  const mayShowReview = user?.is_staff !== false && isHandinConfigured()

  const latest = React.useMemo(
    () => (versions.length ? [...versions].sort((a, b) => a.version_number - b.version_number)[versions.length - 1] : null),
    [versions],
  )
  const [review, setReview] = React.useState<ReviewFacts>(null)
  const [now, setNow] = React.useState(() => Date.now())

  const latestId = latest?.id
  const status = latest?.processing_status
  const latestNumber = latest?.version_number

  React.useEffect(() => {
    setReview(null)
    if (!latestId || status !== 'ready') return
    if (!mayShowReview) {
      setReview('off')
      return
    }
    let cancelled = false
    let timer: ReturnType<typeof setInterval> | undefined
    async function ask() {
      const r = reconcileWithVersion(await fetchReviewStage(assetId), latestNumber)
      if (cancelled) return
      setReview(r)
      const terminal = r === 'off' || (typeof r === 'object' && r !== null && (r.stage === 'done' || r.stage === 'failed' || r.stage === 'skipped'))
      if (terminal && timer) clearInterval(timer)
    }
    void ask()
    timer = setInterval(ask, REVIEW_POLL_MS)
    return () => {
      cancelled = true
      if (timer) clearInterval(timer)
    }
  }, [assetId, latestId, latestNumber, status, mayShowReview])

  React.useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), TICK_MS)
    return () => clearInterval(t)
  }, [])

  if (!latest) return null

  const startedAt = Date.parse(latest.created_at)
  const reviewFacts: ReviewFacts = !mayShowReview ? 'off' : status === 'ready' ? review : null
  const view = computeStages({
    file: fileFacts(status),
    startedAt: Number.isFinite(startedAt) ? startedAt : undefined,
    review: reviewFacts,
    now,
  })

  // Nothing to say: the review is not part of this build or this viewer's screen, and the file is fine.
  if (status === 'ready' && reviewFacts === 'off') return null
  const fresh = Number.isFinite(startedAt) && now - startedAt < FRESH_MS
  if (view.terminal && !view.problem && !fresh) return null

  return (
    <div data-testid="version-stage" className="px-4 py-2 border-b border-border bg-bg-secondary shrink-0">
      <StageStrip view={view} />
    </div>
  )
}
