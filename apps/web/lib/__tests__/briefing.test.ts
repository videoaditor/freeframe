import { expect, it } from 'vitest'
import { briefingFilePayload } from '../briefing'

it('reads Markdown as text rather than sending it as a PDF', async () => {
  const file = new File(['# Launch\nShow the logo.'], 'brief.md', { type: 'text/markdown' })
  expect(await briefingFilePayload(file)).toEqual({ text: '# Launch\nShow the logo.' })
})
it('encodes PDFs and rejects unsupported or oversized files', async () => {
  expect(await briefingFilePayload(new File(['pdf'], 'brief.pdf', { type: 'application/pdf' }))).toEqual({ pdf_base64: 'cGRm' })
  await expect(briefingFilePayload(new File(['x'], 'brief.exe'))).rejects.toThrow('PDF, Markdown')
  const large = new File(['x'], 'brief.md'); Object.defineProperty(large, 'size', { value: 10 * 1024 * 1024 + 1 })
  await expect(briefingFilePayload(large)).rejects.toThrow('10 MB')
})
it('rejects an empty text briefing', async () => {
  await expect(briefingFilePayload(new File(['  '], 'brief.txt'))).rejects.toThrow('empty')
})
