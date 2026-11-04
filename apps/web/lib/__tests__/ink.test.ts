import { describe, expect, it } from 'vitest'
import { DOT_PX, INK_MS, buildDrawingData, classifyMark, clamp01, normalizePoint, isInk } from '../ink'

describe('ink', () => {
  it('normalises to the visible frame, origin top-left, clamped to 0..1', () => {
    const rect = { left: 100, top: 50, width: 200, height: 400 }
    expect(normalizePoint(rect, 200, 250)).toEqual([0.5, 0.5])
    expect(normalizePoint(rect, 100, 50)).toEqual([0, 0])
    expect(normalizePoint(rect, 9999, -5)).toEqual([1, 0])
    expect(clamp01(-1)).toBe(0)
  })
  it('a tap under DOT_PX is a dot, a drag a stroke', () => {
    expect(classifyMark(DOT_PX - 1)).toBe('dot')
    expect(classifyMark(DOT_PX)).toBe('stroke')
  })
  it('keeps the first mark offset and ms precision on t', () => {
    const d = buildDrawingData([
      { k: 'stroke', pts: [[0, 0], [1, 1]], t: 3.14159, offset_ms: 1200 },
      { k: 'dot', pts: [[0.5, 0.5]], t: 4, offset_ms: 2500 },
    ])
    expect(d).toMatchObject({ format: 'ink.v1', mark_offset_ms: 1200 })
    expect((d!.marks as { t: number }[])[0].t).toBe(3.142)
    expect(isInk(d)).toBe(true)
  })
  it('is null without marks and fabric data is not ink', () => {
    expect(buildDrawingData([])).toBeNull()
    expect(isInk({ objects: [] })).toBe(false)
    expect(INK_MS).toBe(1200)
  })
})
