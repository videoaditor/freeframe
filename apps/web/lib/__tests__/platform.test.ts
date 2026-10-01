import { describe, it, expect } from 'vitest'
import { timecode, humanDuration, hours, formatBytes, statusLabel, sliceRanges, TRY_PART_BYTES } from '../platform'

describe('timecode', () => {
  it('formats like a video player', () => {
    expect(timecode(7)).toBe('0:07')
    expect(timecode(83.9)).toBe('1:23')
    expect(timecode(3725)).toBe('1:02:05')
  })
  it('says nothing for an untimed note', () => {
    expect(timecode(null)).toBe('')
    expect(timecode(undefined)).toBe('')
  })
})

describe('time saved, in words', () => {
  it('never shows 0 min', () => {
    expect(humanDuration(20)).toBe('under a minute')
  })
  it('reads naturally', () => {
    expect(humanDuration(48 * 60)).toBe('48 min')
    expect(humanDuration(12 * 3600 + 5 * 60)).toBe('12 h 5 min')
    expect(humanDuration(2 * 3600)).toBe('2 h')
  })
  it('gives the hero number one decimal until it is big', () => {
    expect(hours(5400)).toBe('1.5')
    expect(hours(40 * 3600)).toBe('40')
  })
})

describe('request status', () => {
  const base = { state: 'live' as const, assets: 2, open_must_fixes: 0 }
  it('waits before anything arrives', () => {
    expect(statusLabel({ ...base, assets: 0, status: 'clear' }).label).toBe('Waiting for files')
  })
  it('says what the editor is doing, in words', () => {
    expect(statusLabel({ ...base, status: 'held', open_must_fixes: 1 })).toEqual({ label: 'Editor is fixing 1 thing', tone: 'warn' })
    expect(statusLabel({ ...base, status: 'held', open_must_fixes: 3 }).label).toBe('Editor is fixing 3 things')
  })
  it('is ready when clear', () => {
    expect(statusLabel({ ...base, status: 'clear' })).toEqual({ label: 'Ready', tone: 'ok' })
  })
  it('shows a closed link as closed, whatever the review says', () => {
    expect(statusLabel({ ...base, state: 'revoked', status: 'held', open_must_fixes: 2 }).label).toBe('Closed')
  })
})

describe('upload slices', () => {
  it('covers the file exactly, with no gap and no overlap', () => {
    const size = TRY_PART_BYTES * 2 + 5
    const r = sliceRanges(size)
    expect(r).toHaveLength(3)
    expect(r[0][0]).toBe(0)
    expect(r[2][1]).toBe(size)
    for (let i = 1; i < r.length; i++) expect(r[i][0]).toBe(r[i - 1][1])
  })
  it('formats sizes', () => {
    expect(formatBytes(2.3 * 1024 * 1024)).toBe('2.3 MB')
    expect(formatBytes(10)).toBe('1 KB')
  })
})


it('labels an unavailable review as a warning instead of ready', () => {
  expect(statusLabel({ assets: 1, state: 'live', status: 'unavailable', open_must_fixes: 0 })).toEqual({label: 'Review unavailable', tone: 'warn'})
})
