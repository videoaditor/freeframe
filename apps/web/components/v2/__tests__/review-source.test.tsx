import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { ReviewList } from '../review-list'

it('shows saved sources directly on private editor review comments', () => {
  render(<ReviewList comments={[{ id: 'c1', t: 2, body: 'Keep the end card visible.', must_fix: true,
    review_source: { schema_version: 'autoreview.comment-source.v1', requirement_id: 'req-1',
      sources: [{ layer: 'briefing', reference_id: 'request-1', source_version: 'v1' }] } }]} />)
  expect(screen.getByLabelText('Requirement sources')).toHaveTextContent('Briefing')
  expect(screen.getByText('Keep the end card visible.')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Jump to 0:02' })).toBeVisible()
})
