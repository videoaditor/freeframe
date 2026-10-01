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
