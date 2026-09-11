/**
 * Client for the review gate at review.aditor.ai, used by the /handin page.
 *
 * Two endpoints, both of which are deliberately incapable of refusing anybody:
 *
 *   POST /api/gate/card    - resolves a Trello card link to its name and brand
 *   GET  /api/gate/review  - the craft review for an uploaded asset, once it exists
 *
 * Neither answers with a verdict, and nothing here derives one. The review is
 * advice the editor reads; the delivery decision stays with the editor. See
 * `components/handin/handin-result.tsx` for the structural half of that promise.
 */

/**
 * Where the gate lives. A build arg rather than a literal so a self-hoster who
 * is not Aditor builds a web image with no Aditor host compiled into it, and so
 * a staging build can point at a staging gate. Empty string = the page is off,
 * which is the default for everyone who does not set it.
 */
export const GATE_BASE = process.env.NEXT_PUBLIC_REVIEW_GATE_URL ?? ''

/** Is the hand-in route configured on this build at all? */
export function isHandinConfigured(): boolean {
  return GATE_BASE.trim().length > 0
}

export interface GateCard {
  /** The card's title. Becomes the project name - the editor never types it. */
  name?: string
  /** Resolved from the card's board, never typed. */
  brand?: string
  /** Whether a briefing exists. Never the briefing text itself - that is client material. */
  hasBriefing?: boolean
  trelloCardId?: string
  /** Name on the card, when Trello records who it is for. */
  editorOnCard?: string
  /** Plain-language explanation when the lookup could not complete. */
  note?: string
}

export type GateReview =
  | { state: 'pending'; note?: string }
  | { state: 'ready'; score?: number; worthFixing?: string[]; niceToHave?: string[] }

/**
 * Resolve a pasted Trello link.
 *
 * The gate answers 200 even when Trello is unreachable or the link is not a
 * card, carrying a `note` that explains what it could not check. A 4xx would
 * read to an editor as "something is wrong with your card, do not upload",
 * which is the opposite of true - so a transport failure here is reported the
 * same calm way rather than thrown. The upload must never wait on Trello.
 */
export async function lookUpCard(url: string): Promise<GateCard> {
  try {
    const res = await fetch(`${GATE_BASE}/api/gate/card`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    })
    if (!res.ok) {
      return { hasBriefing: false, note: 'Could not reach the review service. Upload anyway - the review will say what it could not check.' }
    }
    return (await res.json()) as GateCard
  } catch {
    return { hasBriefing: false, note: 'Could not reach the review service. Upload anyway - the review will say what it could not check.' }
  }
}

/**
 * The review for one asset.
 *
 * A failure to fetch is reported as `pending`, never as an error state the page
 * could treat as "no link for you". The worst thing this function may do to an
 * editor is leave them reading "not back yet" next to a link that already works.
 */
export async function fetchReview(assetId: string): Promise<GateReview> {
  try {
    const res = await fetch(`${GATE_BASE}/api/gate/review?asset=${encodeURIComponent(assetId)}`)
    if (!res.ok) {
      return { state: 'pending', note: 'The review will appear here when it is ready.' }
    }
    const data = (await res.json()) as GateReview
    if (data && data.state === 'ready') return data
    return { state: 'pending', note: (data as { note?: string })?.note ?? 'The review will appear here when it is ready.' }
  } catch {
    return { state: 'pending', note: 'The review will appear here when it is ready.' }
  }
}
