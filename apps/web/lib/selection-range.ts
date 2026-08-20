/** Inclusive range of ids between anchorId and targetId, in `ids` order. Null if either id isn't present. */
export function getRangeSelection(ids: string[], anchorId: string, targetId: string): string[] | null {
  const anchorIndex = ids.indexOf(anchorId)
  const targetIndex = ids.indexOf(targetId)
  if (anchorIndex === -1 || targetIndex === -1) return null

  const [start, end] = anchorIndex < targetIndex ? [anchorIndex, targetIndex] : [targetIndex, anchorIndex]
  return ids.slice(start, end + 1)
}
