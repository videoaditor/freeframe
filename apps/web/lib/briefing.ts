import { fileToBase64 } from './platform'

export const BRIEFING_ACCEPT = '.docx,.pdf,.md,.markdown,.txt,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/pdf,text/markdown,text/plain'
export const BRIEFING_HINT = 'Word (.docx), PDF, Markdown or text · 10 MB per file · 20,000 text characters'
export const GUIDELINE_HINT = 'Word (.docx), PDF, Markdown or text · 10 MB per file · 12,000 text characters'

export function validateBriefingText(value: string, kind: 'Briefing' | 'Guidelines' = 'Briefing'): string {
  const text = value.trim()
  if (/[\u0000-\u0008\u000b\u000e-\u001f\u007f-\u009f]/.test(text)) throw new Error('This document contains unreadable characters. Save it as UTF-8 or paste readable text.')
  const limit = kind === 'Guidelines' ? 12_000 : 20_000
  if (text.length > limit) throw new Error(`${kind === 'Guidelines' ? kind : 'Briefings'} can contain up to ${limit.toLocaleString('en-US')} characters. Shorten the text and try again.`)
  return text
}

/** One source field on the API: never silently discard a second document link. */
export function briefingTextPayload(value: string, kind: 'Briefing' | 'Guidelines' = 'Briefing'): { text: string; url?: string } {
  const links: string[] = []
  const text = value.replace(/https?:\/\/(?:(?!,https?:\/\/)[^\s<>"'])*/gi, (raw, offset: number) => {
    let link = raw.replace(/[.,;!]+$/, '')
    for (const [open, close] of [['(', ')'], ['[', ']'], ['{', '}']]) {
      while (link.endsWith(close) && link.split(close).length > link.split(open).length) link = link.slice(0, -1)
    }
    const start = value.lastIndexOf('\n', offset - 1) + 1
    const end = value.indexOf('\n', offset + raw.length)
    const standalone = value.slice(start, end < 0 ? value.length : end).trim() === raw
    let url: URL
    try { url = new URL(link) } catch {
      if (!standalone) return raw
      throw new Error('Use a complete document link starting with https://.')
    }
    const document = (url.hostname === 'docs.google.com' && /^\/document\//.test(url.pathname)) || /\.(pdf|docx?|txt|md|markdown)$/i.test(url.pathname)
    if (!standalone && !document) return raw
    links.push(link)
    return standalone ? '' : raw.slice(link.length)
  })
  const unique = Array.from(new Set(links))
  if (unique.length > 1) throw new Error('Add one document link at a time. Combine the documents into one brief to include every source.')
  return { text: validateBriefingText(text, kind), ...(unique[0] ? { url: unique[0] } : {}) }
}

export async function briefingFilePayload(file: File, kind: 'Briefing' | 'Guidelines' = 'Briefing'): Promise<{ text?: string; pdf_base64?: string; docx_base64?: string }> {
  if (!file.size) throw new Error('This briefing is empty. Add some text first.')
  if (file.size > 10 * 1024 * 1024) throw new Error('Choose a briefing smaller than 10 MB.')
  if (/\.docx$/i.test(file.name)) return { docx_base64: await fileToBase64(file) }
  if (file.type === 'application/pdf' || /\.pdf$/i.test(file.name)) return { pdf_base64: await fileToBase64(file) }
  if (!/\.(md|markdown|txt)$/i.test(file.name)) throw new Error('Choose a Word (.docx), PDF, Markdown (.md), or text file.')
  const bytes = await new Promise<Uint8Array>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer))
    reader.onerror = () => reject(new Error('Could not read this file. Please try again.'))
    reader.readAsArrayBuffer(file)
  })
  const encoding = bytes[0] === 0xff && bytes[1] === 0xfe ? 'utf-16le' : bytes[0] === 0xfe && bytes[1] === 0xff ? 'utf-16be' : 'utf-8'
  let decoded: string
  try { decoded = new TextDecoder(encoding, { fatal: true }).decode(bytes) }
  catch {
    if (encoding !== 'utf-8') throw new Error('Could not read this text file. Save it as UTF-8 and try again.')
    decoded = new TextDecoder('windows-1252').decode(bytes)
  }
  const text = validateBriefingText(decoded, kind)
  if (!text) throw new Error('This briefing is empty. Add some text first.')
  return { text }
}

export function briefingFilenameTitle(name: string): string {
  return name.replace(/\.(docx|pdf|md|markdown|txt)$/i, '').replace(/[_]+/g, ' ').trim().slice(0, 255)
}

export function briefingLinkTitle(value: string): string | null {
  try {
    const url = new URL(value)
    if (!['http:', 'https:'].includes(url.protocol) || /(^|\.)(google\.com|sharepoint\.com)$/.test(url.hostname)) return null
    const part = decodeURIComponent(url.pathname.split('/').filter(Boolean).pop() || '').replace(/-[a-f0-9]{32}$/i, '')
    if (!/[ _-]/.test(part) || !/[a-z]{3}/i.test(part)) return null
    return briefingFilenameTitle(part).replace(/-/g, ' ').trim() || null
  } catch { return null }
}
