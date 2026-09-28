import { expect, it } from 'vitest'
import { editorAccuracy, type EditorStats } from '../platform'
const editor = (email: string, rate: number | null, rated = 10): EditorStats => ({ email, name: email, videos: 30, rated, first_try_rate: rate, avg_versions: 1, open_must_fixes: 0 })
it('averages editors equally, excludes unknowns and rounds only for display', () => {
  const result = editorAccuracy([editor('a', .917, 24), editor('b', .789, 38), editor('c', .5, 2), editor('unknown', null, 0)])
  expect(result.average).toBeCloseTo(.7353333)
  expect(result.count).toBe(3)
  expect(result.outliers).toEqual([])
})
it('flags both directions using unrounded rates and sufficient samples', () => {
  const result = editorAccuracy([editor('high', 1), editor('middle', .6), editor('low', .2)])
  expect(result.average).toBeCloseTo(.6)
  expect(result.outliers.map(o => [o.email, o.direction])).toEqual([['high', 'above'], ['low', 'below']])
})
it('does not flag small samples, a small team, or ordinary variation', () => {
  expect(editorAccuracy([editor('a', 1), editor('b', 0)]).outliers).toEqual([])
  expect(editorAccuracy([editor('a', .8), editor('b', .8), editor('c', .8), editor('small', .1, 2)]).outliers).toEqual([])
  expect(editorAccuracy([editor('a', .9), editor('b', .8), editor('c', .7)]).outliers).toEqual([])
})
it('keeps no data separate from a real zero average', () => {
  expect(editorAccuracy([editor('unknown', null, 0)]).average).toBeNull()
  expect(editorAccuracy([editor('a', 0)]).average).toBe(0)
})
