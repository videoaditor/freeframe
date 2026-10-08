'use client'
import * as React from 'react'
import { ClipboardPaste, FileText, X } from 'lucide-react'
import { BRIEFING_ACCEPT } from '@/lib/briefing'
import { DropZone } from './drop-zone'
import styles from './autoreview-setup.module.css'

export function BriefInput({ file, onFile, text, onText, disabled }: {
  file: File | null; onFile: (file: File | null) => void
  text: string; onText: (text: string) => void; disabled?: boolean
}) {
  const [showLink, setShowLink] = React.useState(/^https?:\/\//i.test(text))
  const [showText, setShowText] = React.useState(!!text && !/^https?:\/\//i.test(text))
  const [notice, setNotice] = React.useState('')
  const link = React.useRef<HTMLInputElement>(null)
  const pending = React.useRef(0)
  React.useEffect(() => () => { pending.current++ }, [])
  async function pasteLink() {
    const operation = ++pending.current
    setShowLink(true); setShowText(false); setNotice('')
    try {
      const value = (await navigator.clipboard.readText()).trim()
      if (operation !== pending.current) return
      const url = new URL(value)
      if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Invalid link')
      onText(value)
    } catch {
      if (operation === pending.current) setNotice('Paste your document link below.')
    }
    if (operation === pending.current) link.current?.focus()
  }
  const hasLink = showLink || /^https?:\/\//i.test(text)
  return <div className={styles.briefInput}>
    <div className={styles.briefDrop}>
      {file ? <div className={styles.file}><FileText size={22} /><span>{file.name}</span><button type="button" aria-label={`Remove ${file.name}`} disabled={disabled} onClick={() => onFile(null)}><X size={18} /></button></div>
        : <DropZone compact disabled={disabled} accept={BRIEFING_ACCEPT} title="Drop your first briefing" hint="PDF, Markdown or text · up to 10 MB" className={styles.briefDropTarget} onFiles={([f]) => { pending.current++; onFile(f) }} />}
      <div className={styles.linkAction}>
        <button type="button" className={styles.pasteButton} disabled={disabled} onClick={() => void pasteLink()}><ClipboardPaste size={17} /> Paste link</button>
        {hasLink && !showText && <input ref={link} aria-label="Briefing link" type="url" pattern="https?://.+" className={styles.input} value={text} disabled={disabled} onChange={e => { pending.current++; onText(e.target.value); setNotice('') }} placeholder="https://docs.google.com/…" />}
        {notice && <p className={styles.note} role="status">{notice}</p>}
        {hasLink && !showText && <p className={styles.note}>Use a link your editor can open.</p>}
      </div>
    </div>
    <button type="button" className={`${styles.textButton} ${styles.textAlternative}`} aria-expanded={showText} aria-controls="brief-text-alternative" disabled={disabled} onClick={() => { pending.current++; setShowLink(false); setShowText(!showText); setNotice('') }}>{showText ? 'Hide text' : 'Paste text instead'}</button>
    {showText && <label id="brief-text-alternative" className={styles.label}>Briefing text<textarea autoFocus aria-label="Briefing text or link" className={styles.input} rows={3} value={text} disabled={disabled} onChange={e => onText(e.target.value)} placeholder="The product, audience, key message, and anything your editor must include." /></label>}
  </div>
}
