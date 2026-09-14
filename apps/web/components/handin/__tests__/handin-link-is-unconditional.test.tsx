import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { HandinResult, ShareLinkPanel } from '../handin-result'
import type { GateReview } from '@/lib/handin'

/**
 * The upload gate has one rule that outranks everything else on the page: the
 * link appears the moment it exists, whatever the review says, and never below
 * the findings.
 *
 * The tool advises and the editor delivers. A build that withheld the link on a
 * bad score would be a different product - a gatekeeper - and that was
 * explicitly not what was agreed. It is the kind of thing that arrives later as
 * a one-line "helpful" condition, so these tests assert the rule from the
 * outside, on rendered output, where such a condition would show up.
 */
describe('hand-in - the share link does not depend on the review', () => {
  afterEach(() => vi.restoreAllMocks())

  const LINK = 'https://freeframe.aditor.ai/share/tok123'

  // The worst review the gate can produce: a rock-bottom score and a list of
  // defects. This is the exact case a score-reading gate would hide the link on.
  const disaster: GateReview = {
    state: 'ready',
    score: 10,
    worthFixing: [
      'Captions are not verbatim to the script.',
      'CTA is missing entirely.',
      'Overlay sits over the speaker head.',
    ],
    niceToHave: ['Add a music bed.'],
  }

  it('shows the link with a 10/100 review that is nothing but defects', () => {
    render(<HandinResult shareUrl={LINK} reviews={[{ review: disaster }]} />)
    expect(screen.getByTestId('handin-share-link')).toBeInTheDocument()
    expect(screen.getByDisplayValue(LINK)).toBeInTheDocument()
  })

  it('shows the link while the review has not come back yet', () => {
    // The ordinary state in the seconds after an upload. "Not reviewed yet" is
    // not a reason to hold somebody's link - they may be posting it right now.
    render(
      <HandinResult
        shareUrl={LINK}
        reviews={[{ review: { state: 'pending', note: 'Still reading the file.' } }]}
      />,
    )
    expect(screen.getByDisplayValue(LINK)).toBeInTheDocument()
    expect(screen.getByText('Still reading the file.')).toBeInTheDocument()
  })

  it('shows the link when the review failed outright and there is no review at all', () => {
    // review === null is what the page holds when the gate is unreachable. A
    // review service being down must never cost an editor their delivery.
    render(<HandinResult shareUrl={LINK} reviews={[{ review: null }]} />)
    expect(screen.getByDisplayValue(LINK)).toBeInTheDocument()
  })

  it('shows the link when several videos were handed in at once', () => {
    // A batch hand-in is one link over many videos. The link is still rendered
    // once, above every review, no matter how many reviews sit below it.
    render(
      <HandinResult
        shareUrl={LINK}
        reviews={[
          { label: 'hook1.mp4', review: disaster },
          { label: 'hook2.mp4', review: { state: 'pending' } },
          { label: 'hook3.mp4', review: null },
        ]}
      />,
    )
    expect(screen.getByDisplayValue(LINK)).toBeInTheDocument()
    expect(screen.getByText('hook1.mp4')).toBeInTheDocument()
    expect(screen.getByText('hook2.mp4')).toBeInTheDocument()
    expect(screen.getByText('hook3.mp4')).toBeInTheDocument()
    expect(screen.getAllByTestId('handin-review')).toHaveLength(3)
  })

  it('puts the link above the findings in the document, not below them', () => {
    // Ordering is part of the rule, not styling. Making somebody scroll past
    // criticism to reach their own link is withholding it by layout - the
    // editor reads the verdict first and the link second, which is the shape of
    // a gate even when nothing is technically hidden.
    const { container } = render(
      <HandinResult shareUrl={LINK} reviews={[{ review: disaster }]} />,
    )
    const html = container.innerHTML
    const linkAt = html.indexOf('handin-share-link')
    const reviewAt = html.indexOf('handin-review')
    expect(linkAt).toBeGreaterThan(-1)
    expect(reviewAt).toBeGreaterThan(-1)
    expect(linkAt).toBeLessThan(reviewAt)
  })

  it('renders the link from the url alone, with no review in scope', () => {
    // ShareLinkPanel takes {url} and nothing else. This is the structural half
    // of the promise: a score cannot be branched on where it is not a prop, so
    // adding a gate here would mean widening the props first - a change a
    // reviewer can see, rather than a condition tucked inside an existing one.
    render(<ShareLinkPanel url={LINK} />)
    expect(screen.getByDisplayValue(LINK)).toBeInTheDocument()
  })
})

describe('hand-in - the findings use the review page headings', () => {
  it('groups findings under "Worth fixing" and "Nice to have"', () => {
    // An editor reads this page and the existing review page about the same
    // video. Different words for the same group read as a different judgement,
    // so these two strings are copied from the review page rather than chosen.
    render(
      <HandinResult
        shareUrl="https://x/share/t"
        reviews={[{
          review: {
            state: 'ready',
            score: 70,
            worthFixing: ['Must fix - CTA missing.'],
            niceToHave: ['Add a music bed.'],
          },
        }]}
      />,
    )
    expect(screen.getByText('Worth fixing')).toBeInTheDocument()
    expect(screen.getByText('Nice to have')).toBeInTheDocument()
    expect(screen.getByText('Must fix - CTA missing.')).toBeInTheDocument()
    expect(screen.getByText('Add a music bed.')).toBeInTheDocument()
  })

  it('does not invent an empty heading when a group has no findings', () => {
    // A bare "Worth fixing" over nothing reads as a truncated list rather than
    // a clean review, which is alarming for no reason.
    render(
      <HandinResult
        shareUrl="https://x/share/t"
        reviews={[{ review: { state: 'ready', score: 95, worthFixing: [], niceToHave: ['Tighten the tail.'] } }]}
      />,
    )
    expect(screen.queryByText('Worth fixing')).not.toBeInTheDocument()
    expect(screen.getByText('Nice to have')).toBeInTheDocument()
  })
})
