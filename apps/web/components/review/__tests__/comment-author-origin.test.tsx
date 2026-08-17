import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { useReviewStore } from '@/stores/review-store'
import { CommentPanel } from '../comment-panel'

// A comment from a client arriving through a share link was rendered exactly like
// one from a teammate: same row, same styling, only a different name - and that
// name is free text the client typed into the prompt, so it proves nothing. The
// distinction is in the data (author_id vs guest_author_id); it just never reached
// the screen.
beforeEach(() => {
  useReviewStore.getState().reset()
  Element.prototype.scrollIntoView = vi.fn()
})

const noop = async () => {}

function makeComment(over: Record<string, unknown>) {
  return {
    id: 'c1', asset_id: 'a1', version_id: 'v1', parent_id: null,
    body: 'The cut lands a beat late', timecode_start: 4, timecode_end: null,
    resolved: false, visibility: 'public',
    created_at: '2026-01-01T10:00:00.000Z', updated_at: '2026-01-01T10:00:00.000Z',
    replies: [], reactions: [], attachments: [],
    ...over,
  } as never
}

const fromTeammate = makeComment({
  id: 'staff',
  author_id: 'u1', guest_author_id: null,
  author: { id: 'u1', name: 'Maya Chen', avatar_url: null },
})

const fromClient = makeComment({
  id: 'guest',
  author_id: null, guest_author_id: 'g1',
  author: null,
  guest_author: { id: 'g1', name: 'Maya Chen', email: 'maya@brand.example' },
})

function renderWith(comments: unknown[]) {
  return render(
    <CommentPanel
      comments={comments as never}
      onResolve={noop} onDelete={noop}
      onAddReaction={noop} onRemoveReaction={noop}
      onReply={() => {}}
    />,
  )
}

describe('CommentPanel marks where a comment came from', () => {
  it('badges a share-link author as a client', () => {
    renderWith([fromClient])
    expect(screen.getByText('Client')).toBeInTheDocument()
  })

  it('leaves an account holder unbadged', () => {
    renderWith([fromTeammate])
    expect(screen.queryByText('Client')).not.toBeInTheDocument()
  })

  it('tells the two apart even when they share a display name', () => {
    // Both render "Maya Chen"; the badge is the only thing separating them.
    renderWith([fromTeammate, fromClient])
    expect(screen.getAllByText('Maya Chen')).toHaveLength(2)
    expect(screen.getAllByText('Client')).toHaveLength(1)
  })
})
