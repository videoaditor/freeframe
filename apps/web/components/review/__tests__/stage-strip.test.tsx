import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StageStrip } from '../stage-strip'
import { computeStages } from '@/lib/stages'

const NOW = 1_800_000_000_000

describe('the stage strip', () => {
  it('shows the four steps in order, marking the active one and its minutes', () => {
    const view = computeStages({ file: 'processing', startedAt: NOW - 12 * 60_000, review: null, now: NOW })
    render(<StageStrip view={view} />)
    const items = screen.getAllByRole('listitem')
    expect(items.map((i) => i.getAttribute('data-testid'))).toEqual([
      'stage-step-upload', 'stage-step-processing', 'stage-step-review', 'stage-step-done',
    ])
    expect(screen.getByTestId('stage-step-processing')).toHaveAttribute('data-state', 'active')
    expect(screen.getByTestId('stage-step-processing')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByTestId('stage-step-processing')).toHaveTextContent('12 min')
    expect(screen.getByTestId('stage-step-upload')).toHaveAttribute('data-state', 'done')
    expect(screen.getByTestId('stage-step-review')).toHaveAttribute('data-state', 'waiting')
  })

  it('a stuck review reads differently from a stuck video', () => {
    const stuckVideo = computeStages({ file: 'processing', startedAt: NOW - 45 * 60_000, review: null, now: NOW })
    const { unmount } = render(<StageStrip view={stuckVideo} />)
    expect(screen.getByTestId('stage-step-processing')).toHaveAttribute('data-state', 'active')
    expect(screen.getByTestId('stage-step-review')).toHaveAttribute('data-state', 'waiting')
    unmount()

    const stuckReview = computeStages({
      file: 'ready', startedAt: NOW - 45 * 60_000, now: NOW,
      review: { stage: 'reading', step: 'analysing', startedAgoSeconds: 20 * 60, quietSeconds: 11 * 60 },
    })
    render(<StageStrip view={stuckReview} />)
    expect(screen.getByTestId('stage-step-processing')).toHaveAttribute('data-state', 'done')
    expect(screen.getByTestId('stage-step-review')).toHaveAttribute('data-state', 'active')
    expect(screen.getByTestId('stage-step-review')).toHaveTextContent('Analysing')
    expect(screen.getByTestId('stage-problem')).toHaveTextContent(/review is taking longer/i)
  })

  it('a failure is announced as an alert, a slow stage as a status', () => {
    const failed = computeStages({ file: 'failed', startedAt: NOW - 60 * 60_000, review: null, now: NOW })
    const { unmount } = render(<StageStrip view={failed} />)
    expect(screen.getByRole('alert')).toHaveTextContent(/failed to process/)
    unmount()
    const slow = computeStages({ file: 'processing', startedAt: NOW - 40 * 60_000, review: null, now: NOW })
    render(<StageStrip view={slow} />)
    expect(screen.getByRole('status')).toHaveTextContent(/taking longer than usual/)
  })

  it('hideProblem leaves the message to the screen that already shows it', () => {
    const failed = computeStages({ file: 'failed', startedAt: NOW - 60 * 60_000, review: null, now: NOW })
    render(<StageStrip view={failed} hideProblem />)
    expect(screen.queryByTestId('stage-problem')).toBeNull()
    expect(screen.getByTestId('stage-step-processing')).toHaveAttribute('data-state', 'failed')
  })

  it('a clean finished review says so', () => {
    const view = computeStages({ file: 'ready', startedAt: NOW - 9 * 60_000, review: { stage: 'done', clean: true }, now: NOW })
    render(<StageStrip view={view} />)
    expect(screen.getByTestId('stage-step-done')).toHaveTextContent('Reviewed: nothing to fix')
  })
})
