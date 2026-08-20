import { describe, it, expect } from 'vitest'
import { getRangeSelection } from '../selection-range'

const ids = ['a', 'b', 'c', 'd', 'e']

describe('getRangeSelection', () => {
  it('selects the inclusive range going forward', () => {
    expect(getRangeSelection(ids, 'b', 'd')).toEqual(['b', 'c', 'd'])
  })

  it('selects the inclusive range going backward', () => {
    expect(getRangeSelection(ids, 'd', 'b')).toEqual(['b', 'c', 'd'])
  })

  it('returns a single id when anchor and target are the same', () => {
    expect(getRangeSelection(ids, 'c', 'c')).toEqual(['c'])
  })

  it('returns null when the anchor is no longer present', () => {
    expect(getRangeSelection(ids, 'missing', 'd')).toBeNull()
  })

  it('returns null when the target is no longer present', () => {
    expect(getRangeSelection(ids, 'b', 'missing')).toBeNull()
  })
})
