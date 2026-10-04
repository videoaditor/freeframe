import React from 'react'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ProgressBar } from '../progress-bar'
import { formatTimecode } from '@/lib/utils'

afterEach(cleanup)

describe('timeline seeking', () => {
  it('seeks forward and backward continuously through native range input events', () => {
    const onSeek = vi.fn()
    render(<ProgressBar currentTime={12} duration={52.5} onSeek={onSeek} />)
    const slider = screen.getByRole('slider', { name: 'Video timeline' })
    fireEvent.input(slider, { target: { value: '36.2' } })
    expect(onSeek).toHaveBeenLastCalledWith(36.2)
    fireEvent.input(slider, { target: { value: '7.1' } })
    expect(onSeek).toHaveBeenLastCalledWith(7.1)
    fireEvent.input(slider, { target: { value: '0' } })
    expect(onSeek).toHaveBeenLastCalledWith(0)
    fireEvent.input(slider, { target: { value: '52.5' } })
    expect(onSeek).toHaveBeenLastCalledWith(52.5)
  })

  it('exposes exact seconds for assistive technology and fine native keyboard steps', () => {
    const onSeek = vi.fn()
    render(<ProgressBar currentTime={15.2} duration={47.8} onSeek={onSeek} />)
    const slider = screen.getByRole('slider', { name: 'Video timeline' })
    expect(slider).toHaveAttribute('aria-valuetext', '15.2 of 47.8 seconds')
    fireEvent.keyDown(slider, { key: 'ArrowRight' })
    expect(onSeek.mock.calls.at(-1)?.[0]).toBeCloseTo(15.3)
    fireEvent.keyDown(slider, { key: 'Home' })
    expect(onSeek).toHaveBeenLastCalledWith(0)
    fireEvent.keyDown(slider, { key: 'End' })
    expect(onSeek).toHaveBeenLastCalledWith(47.8)
    expect(slider).toHaveAttribute('value', '15.2')
  })

  it('does not allow seeking before a usable duration is known', () => {
    const { rerender } = render(<ProgressBar currentTime={0} duration={0} onSeek={vi.fn()} />)
    expect(screen.getByRole('slider')).toBeDisabled()
    rerender(<ProgressBar currentTime={0} duration={NaN} onSeek={vi.fn()} />)
    expect(screen.getByRole('slider')).toBeDisabled()
  })

  it('clamps a stale playhead to a shorter replacement clip', () => {
    render(<ProgressBar currentTime={52} duration={10} onSeek={vi.fn()} />)
    expect(screen.getByRole('slider')).toHaveAttribute('value', '10')
  })
  it('does not cover the video with a mouse-compatible hover preview after touch movement', () => {
    render(<ProgressBar currentTime={12} duration={52.5} onSeek={vi.fn()} />)
    const slider = screen.getByRole('slider')
    const touchMove = new MouseEvent('pointermove', { bubbles: true, clientX: 100 })
    Object.defineProperty(touchMove, 'pointerType', { value: 'touch' })
    fireEvent(slider, touchMove)
    fireEvent.mouseMove(slider, { clientX: 100 })
    expect(screen.queryByText(formatTimecode(52.5))).not.toBeInTheDocument()
  })

  it('retains the desktop mouse hover time preview', () => {
    render(<ProgressBar currentTime={12} duration={52.5} onSeek={vi.fn()} />)
    const slider = screen.getByRole('slider')
    const mouseMove = new MouseEvent('pointermove', { bubbles: true, clientX: 100 })
    Object.defineProperty(mouseMove, 'pointerType', { value: 'mouse' })
    fireEvent(slider, mouseMove)
    fireEvent.mouseMove(slider, { clientX: 100 })
    expect(screen.getByText(formatTimecode(52.5))).toBeInTheDocument()
  })

})
