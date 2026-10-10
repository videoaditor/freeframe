import { expect, it } from 'vitest'
import { briefingFilePayload, briefingFilenameTitle, briefingTextPayload } from '../briefing'

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


it.each([
  ['UTF-8', new Uint8Array([0x43,0x61,0x66,0xc3,0xa9])],
  ['UTF-8 BOM', new Uint8Array([0xef,0xbb,0xbf,0x43,0x61,0x66,0xc3,0xa9])],
  ['UTF-16 LE BOM', new Uint8Array([0xff,0xfe,0x43,0,0x61,0,0x66,0,0xe9,0])],
  ['UTF-16 BE BOM', new Uint8Array([0xfe,0xff,0,0x43,0,0x61,0,0x66,0,0xe9])],
  ['Windows-1252', new Uint8Array([0x43,0x61,0x66,0xe9])],
] as const)('audit reads %s TXT without losing accents', async (_name, bytes) => {
  expect(await briefingFilePayload(new File([bytes], 'guide.txt'))).toEqual({text:'Café'})
})
it('audit rejects binary text and text beyond the complete briefing budget', async () => {
  await expect(briefingFilePayload(new File([new Uint8Array([0,1,2])],'brief.txt'))).rejects.toThrow('readable text')
  await expect(briefingFilePayload(new File(['x'.repeat(20001)],'brief.txt'))).rejects.toThrow('20,000')
})
it('audit separates a single source link and notes, and rejects multiple source links', () => {
  expect(briefingTextPayload('Keep the logo.\nhttps://docs.google.com/document/d/abc/edit')).toEqual({text:'Keep the logo.',url:'https://docs.google.com/document/d/abc/edit'})
  expect(() => briefingTextPayload('https://docs.google.com/document/d/a/edit\nhttps://drive.google.com/file/d/b/view')).toThrow('one document link')
})


it.each(['brief.docx','brief.pdf','brief.txt'])('rejects a zero-byte %s instead of creating a request with no briefing', async name => {
  await expect(briefingFilePayload(new File([],name))).rejects.toThrow('empty')
})


it.each(['Always show https://fortea.com on the end card.', 'Compare https://one.example/product and https://two.example/product in the opening shot.'])('keeps incidental instruction URLs as text: %s', text => {
  expect(briefingTextPayload(text)).toEqual({text})
})


it.each(['Use b-roll from https://drive.google.com/drive/folders/abc in scene 2.', 'Use the product video https://drive.google.com/file/d/abc/view for the opening shot.'])('preserves inline Drive media references: %s', text => {
  expect(briefingTextPayload(text)).toEqual({text})
})

it('rejects comma-separated document sources without dropping the second source', () => {
  expect(() => briefingTextPayload('https://docs.google.com/document/d/a/edit,https://docs.google.com/document/d/b/edit')).toThrow('one document link')
})

it('preserves commas inside a single signed document URL', () => {
  const url = 'https://example.com/brief.pdf?signature=first,second'
  expect(briefingTextPayload(url)).toEqual({text: '', url})
})
