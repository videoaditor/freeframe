import type { ReviewComment } from './platform'

const stamp = (seconds: number) => {
  const ms = Math.max(0, Math.round(seconds * 1000))
  return `${String(Math.floor(ms / 3600000)).padStart(2, '0')}:${String(Math.floor(ms / 60000) % 60).padStart(2, '0')}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')},${String(ms % 1000).padStart(3, '0')}`
}
export function feedbackSrt(comments: ReviewComment[], duration?: number | null) {
  const timed = comments.filter(c => c.t !== null && Number.isFinite(c.t) && c.t >= 0 && (!duration || c.t < duration)).sort((a, b) => a.t! - b.t!)
  return timed.map((c, i) => `${i + 1}\n${stamp(c.t!)} --> ${stamp(Math.min(c.t! + 3, duration || Infinity))}\n[${c.must_fix || c.weight === 'must_fix' ? 'FIX' : 'OPTIONAL'}] ${c.body.replace(/\r?\n\s*\r?\n/g, '\n')}\n`).join('\n')
}
export function downloadFeedback(name: string, comments: ReviewComment[], duration?: number | null, format: 'srt' | 'txt' = 'srt') {
  const text = format === 'srt' ? feedbackSrt(comments, duration) : comments.map(c => `${c.t === null ? 'Whole video' : stamp(c.t)} · ${c.body}`).join('\n\n')
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }))
  const a = document.createElement('a'); a.href = url; a.download = `${name.replace(/\.[^.]+$/, '')}-feedback.${format}`; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
