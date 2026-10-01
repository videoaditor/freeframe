import { expect, it } from 'vitest'
import { feedbackSrt } from '../request-feedback'
it('exports source-timed feedback, clips at duration and leaves untimed notes for TXT', () => {
  const srt = feedbackSrt([{ t: null, body: 'Whole cut' }, { t: 4.25, body: 'Fix ending', must_fix: true }, { t: 0, body: 'Optional' }], 5)
  expect(srt).toContain('00:00:04,250 --> 00:00:05,000\n[FIX] Fix ending')
  expect(srt).not.toContain('Whole cut')
  expect(srt.startsWith('1\n00:00:00,000')).toBe(true)
})
