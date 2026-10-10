import { expect, it } from 'vitest'
import { briefingFilePayload, briefingFilenameTitle } from '../briefing'

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

it('accepts Word documents even when the browser reports generic binary MIME', async () => {
  const file = new File(['docx'], 'Brief.DOCX', { type: 'application/octet-stream' })
  expect(await briefingFilePayload(file)).toEqual({ docx_base64: 'ZG9jeA==' })
})

it('uses a Word filename as the project title without its extension', () => {
  expect(briefingFilenameTitle('example_briefing_ad_19.DOCX')).toBe('example briefing ad 19')
})
