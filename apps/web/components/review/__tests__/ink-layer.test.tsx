import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { InkLayer } from '../ink-layer'

afterEach(() => { cleanup(); vi.useRealTimers() })
const draw = (layer: HTMLElement) => {
  layer.getBoundingClientRect = () => ({ left: 0, top: 0, width: 200, height: 400, right: 200, bottom: 400, x: 0, y: 0, toJSON: () => ({}) })
  fireEvent.pointerDown(layer, { clientX: 10, clientY: 10, pointerId: 1 })
  fireEvent.pointerMove(layer, { clientX: 80, clientY: 120, pointerId: 1 })
  fireEvent.pointerMove(layer, { clientX: 150, clientY: 200, pointerId: 1 })
  fireEvent.pointerUp(layer, { clientX: 150, clientY: 200, pointerId: 1 })
}
const strokes = (c: HTMLElement) => c.querySelectorAll('.ink-stroke')

describe('InkLayer persistence', () => {
  it('keeps a stroke fully visible while the video is paused, with no timer', () => {
    vi.useFakeTimers()
    const { getByTestId, container } = render(<InkLayer active playing={false} onStart={() => {}} onMark={() => {}} />)
    draw(getByTestId('ink-layer'))
    expect(strokes(container)).toHaveLength(1)
    act(() => { vi.advanceTimersByTime(10_000) })
    expect(strokes(container)).toHaveLength(1)
    expect(container.querySelector('.ink-stroke')).not.toHaveAttribute('data-fading')
  })

  it('fades out when playback resumes and is gone a few hundred ms later', () => {
    vi.useFakeTimers()
    const { getByTestId, container, rerender } = render(<InkLayer active playing={false} onStart={() => {}} onMark={() => {}} />)
    draw(getByTestId('ink-layer'))
    rerender(<InkLayer active playing onStart={() => {}} onMark={() => {}} />)
    expect(container.querySelector('.ink-stroke')).toHaveAttribute('data-fading')
    act(() => { vi.advanceTimersByTime(300) })
    expect(strokes(container)).toHaveLength(0)
  })

  it('hides instantly under reduced motion', () => {
    vi.useFakeTimers()
    window.matchMedia = vi.fn().mockReturnValue({ matches: true, addEventListener() {}, removeEventListener() {} }) as never
    const { getByTestId, container, rerender } = render(<InkLayer active playing={false} onStart={() => {}} onMark={() => {}} />)
    draw(getByTestId('ink-layer'))
    rerender(<InkLayer active playing onStart={() => {}} onMark={() => {}} />)
    act(() => { vi.advanceTimersByTime(1) })
    expect(strokes(container)).toHaveLength(0)
  })

  it('a replayed stroke stays until playback resumes, then fades', () => {
    vi.useFakeTimers()
    window.matchMedia = vi.fn().mockReturnValue({ matches: false, addEventListener() {}, removeEventListener() {} }) as never
    const replay = { key: 1, marks: [{ k: 'stroke' as const, points: [[0, 0], [0.5, 0.5], [1, 1]] as [number, number][] }] }
    const { container, rerender } = render(<InkLayer active={false} playing={false} replay={replay} onStart={() => {}} onMark={() => {}} />)
    expect(strokes(container)).toHaveLength(1)
    act(() => { vi.advanceTimersByTime(5000) })
    expect(strokes(container)).toHaveLength(1)
    rerender(<InkLayer active={false} playing replay={replay} onStart={() => {}} onMark={() => {}} />)
    act(() => { vi.advanceTimersByTime(300) })
    expect(strokes(container)).toHaveLength(0)
  })

  it('draws a darker contour under the white core so it reads on bright frames', () => {
    const { getByTestId, container } = render(<InkLayer active playing={false} onStart={() => {}} onMark={() => {}} />)
    draw(getByTestId('ink-layer'))
    const g = container.querySelector('.ink-stroke')!
    const kids = Array.from(g.children).map(c => c.getAttribute('class'))
    expect(kids.indexOf('ink-contour')).toBeLessThan(kids.indexOf('ink-line'))
    const contour = g.querySelector('.ink-contour') as SVGElement
    const core = g.querySelector('.ink-line') as SVGElement
    expect(parseFloat(contour.style.strokeWidth) - parseFloat(core.style.strokeWidth)).toBe(3)
  })

  it('drawn strokes are smooth curves, not polylines', () => {
    const { getByTestId, container } = render(<InkLayer active playing={false} onStart={() => {}} onMark={() => {}} />)
    draw(getByTestId('ink-layer'))
    expect(container.querySelector('.ink-line')?.getAttribute('d')).toMatch(/Q/)
  })
})
