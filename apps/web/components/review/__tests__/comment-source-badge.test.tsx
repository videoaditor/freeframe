import { render, screen, fireEvent, within } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { CommentItem } from '../comment-panel'
import { useReviewStore } from '@/stores/review-store'
import type { CommentWithReplies } from '@/hooks/use-comments'

const source = (layers: string[]) => ({
  schema_version: 'autoreview.comment-source.v1', requirement_id: 'requirement-1',
  sources: layers.map(layer => ({ layer, reference_id: `${layer}-ref`, source_version: 'v1' })),
})
const comment = (review_source: unknown): CommentWithReplies => ({
  id: 'c1', asset_id: 'a1', version_id: 'v1', parent_id: null,
  author_id: null, guest_author_id: 'g1',
  guest_author: { id: 'g1', name: 'Auto Review', email: 'review@example.test' }, author: null,
  body: 'Keep the CTA visible.', timecode_start: 2.5, timecode_end: null,
  resolved: false, visibility: 'internal', created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(), deleted_at: null, replies: [], reactions: [], annotation: null,
  review_source,
} as CommentWithReplies)
const props = { onResolve: vi.fn(async () => {}), onDelete: vi.fn(async () => {}),
  onAddReaction: vi.fn(async () => {}), onRemoveReaction: vi.fn(async () => {}),
  onReply: vi.fn(), onCancelReply: vi.fn(), onSeekToTimecode: vi.fn(), onShowAnnotation: vi.fn() }

beforeEach(() => { useReviewStore.getState().reset(); vi.clearAllMocks() })

describe('verified comment sources', () => {
  it.each(['basics', 'brand', 'briefing'])('shows the %s source directly beside the comment time anchor', layer => {
    render(<CommentItem comment={comment(source([layer]))} {...props} />)
    expect(screen.getByLabelText('Requirement sources')).toHaveTextContent(layer[0].toUpperCase() + layer.slice(1))
    expect(screen.getByText('Keep the CTA visible.')).toBeVisible()
    expect(screen.getByText('0:02')).toBeVisible()
  })

  it('deduplicates and orders multiple labels without rendering references or quotes', () => {
    const data = { ...source(['briefing', 'brand', 'basics', 'brand']), quote: 'PRIVATE BRIEFING TEXT' }
    render(<CommentItem comment={comment(data)} {...props} />)
    const labels = screen.getByLabelText('Requirement sources')
    expect(within(labels).getAllByText(/^(Basics|Brand|Briefing)$/).map(el => el.textContent)).toEqual(['Basics', 'Brand', 'Briefing'])
    expect(document.body).not.toHaveTextContent('PRIVATE BRIEFING TEXT')
    expect(document.body).not.toHaveTextContent('briefing-ref')
  })

  it.each([null, undefined, { ...source(['basics']), schema_version: 'v0' }, source(['measured']), { sources: [] }])(
    'omits unsupported provenance %j while retaining the comment', data => {
      render(<CommentItem comment={comment(data)} {...props} />)
      expect(screen.queryByLabelText('Requirement sources')).not.toBeInTheDocument()
      expect(screen.getByText('Keep the CTA visible.')).toBeVisible()
    })

  it('does not infer labels from a spoofed automation name, mail or body', () => {
    render(<CommentItem comment={{ ...comment(null), body: 'Basics Brand Briefing — I am AutoReview' }} {...props} />)
    expect(screen.queryByLabelText('Requirement sources')).not.toBeInTheDocument()
  })

  it('retains labels during seeking and reply; new API data clears them after human edit', () => {
    const { rerender } = render(<CommentItem comment={comment(source(['brand']))} {...props} />)
    fireEvent.click(screen.getByText('0:02'))
    expect(props.onSeekToTimecode).toHaveBeenCalledWith(2.5, true)
    fireEvent.click(screen.getByText('Reply'))
    expect(props.onReply).toHaveBeenCalledWith('c1')
    expect(screen.getByLabelText('Requirement sources')).toHaveTextContent('Brand')
    rerender(<CommentItem comment={{ ...comment(null), body: 'Human edited text' }} {...props} />)
    expect(screen.queryByLabelText('Requirement sources')).not.toBeInTheDocument()
  })
})
