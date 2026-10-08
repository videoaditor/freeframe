import { fileToBase64 } from './platform'

export const BRIEFING_ACCEPT = '.pdf,.md,.markdown,.txt,application/pdf,text/markdown,text/plain'

export async function briefingFilePayload(file: File): Promise<{ text?: string; pdf_base64?: string }> {
  if (file.size > 10 * 1024 * 1024) throw new Error('Choose a briefing smaller than 10 MB.')
  if (file.type === 'application/pdf' || (!file.type && /\.pdf$/i.test(file.name))) return { pdf_base64: await fileToBase64(file) }
  if (!/\.(md|markdown|txt)$/i.test(file.name)) throw new Error('Choose a PDF, Markdown (.md), or text file.')
  const text = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).trim())
    reader.onerror = () => reject(new Error('Could not read this file. Please try again.'))
    reader.readAsText(file)
  })
  if (!text) throw new Error('This briefing is empty. Add some text first.')
  return { text }
}

export function briefingFilenameTitle(name: string): string {
  return name.replace(/\.(pdf|md|markdown|txt)$/i, '').replace(/[_]+/g, ' ').trim().slice(0, 255)
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
