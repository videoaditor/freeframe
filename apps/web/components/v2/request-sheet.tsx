'use client'

/**
 * "Request files" - Dropbox's file request, with the review built in.
 *
 * One sheet, three answers, one button (Hick): which brand, what it is, the briefing. The briefing is
 * optional - without it the review still checks the brand and best practice - so it never blocks.
 * The end state is the link itself, with Copy as the obvious next step (peak-end).
 */
import * as React from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import useSWR from 'swr'
import { Check, Copy, FileText, Link2, X } from 'lucide-react'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth-store'
import { createRequest, fileToBase64, type FileRequest } from '@/lib/platform'
import type { Project } from '@/types'
import { cn } from '@/lib/utils'
import { DropZone } from './drop-zone'

export function RequestSheet({ open, onOpenChange, onCreated }: {
  open: boolean
  onOpenChange: (v: boolean) => void
  onCreated?: (r: FileRequest) => void
}) {
  const user = useAuthStore((s) => s.user)
  const isCustomer = user?.is_staff === false
  const { data: projects, mutate } = useSWR<Project[]>(open ? '/projects' : null, (k: string) => api.get<Project[]>(k))
  // Staff file into brand workspaces; a customer's own projects are all theirs.
  const brands = React.useMemo(
    () => (projects || []).filter((p) => isCustomer || p.is_workspace).sort((a, b) => a.name.localeCompare(b.name)),
    [projects, isCustomer],
  )

  const [projectId, setProjectId] = React.useState('')
  const [newBrand, setNewBrand] = React.useState('')
  const [title, setTitle] = React.useState('')
  const [briefFile, setBriefFile] = React.useState<File | null>(null)
  const [briefText, setBriefText] = React.useState('')
  const [pasting, setPasting] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState('')
  const [created, setCreated] = React.useState<FileRequest | null>(null)
  const [copied, setCopied] = React.useState(false)
  const titleRef = React.useRef<HTMLInputElement>(null)
  const brandRef = React.useRef<HTMLInputElement>(null)

  // Sensible default (the only brand, or the first) - and a fresh form every time it opens.
  React.useEffect(() => {
    if (!open) return
    setCreated(null); setTitle(''); setBriefFile(null); setBriefText(''); setError(''); setCopied(false); setPasting(false)
  }, [open])
  React.useEffect(() => { if (!projectId && brands.length) setProjectId(brands[0].id) }, [brands, projectId])
  // Only once the list has loaded - otherwise the brand-name field flashes up and steals focus.
  const needsBrand = !!projects && !brands.length
  // Focus the first thing to TYPE, not the first thing to tab to (the brand picker is prefilled).
  React.useEffect(() => {
    if (open && projects && !created) requestAnimationFrame(() => (needsBrand ? brandRef : titleRef).current?.focus())
  }, [open, projects, needsBrand, created])

  const canSubmit = title.trim().length > 0 && (needsBrand ? newBrand.trim().length > 0 : !!projectId) && !busy

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setBusy(true); setError('')
    try {
      let pid = projectId
      if (needsBrand) {
        const p = await api.post<Project>('/projects', { name: newBrand.trim(), project_type: 'team', is_workspace: true })
        pid = p.id
        await mutate()
      }
      const text = briefText.trim()
      const r = await createRequest({
        project_id: pid,
        title: title.trim(),
        brief_text: /^https?:\/\//i.test(text) ? '' : text,
        brief_url: /^https?:\/\//i.test(text) ? text : '',
        brief_pdf_base64: briefFile ? await fileToBase64(briefFile) : '',
      })
      setCreated(r)
      onCreated?.(r)
    } catch (err) {
      // Keep everything they typed; say what to do (Postel).
      setError(err instanceof Error ? err.message : 'That did not work. Try again.')
    } finally {
      setBusy(false)
    }
  }

  const copy = async () => {
    if (!created) return
    await navigator.clipboard.writeText(created.url).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-[2px] fade-in" />
        <Dialog.Content
          // Focus the first thing to TYPE, not the first thing to tab to (the brand picker is prefilled).
          onOpenAutoFocus={(e) => e.preventDefault()}
          className="glass sheet-in fixed inset-x-0 bottom-0 z-50 mx-auto max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-b-none p-6 outline-none sm:bottom-auto sm:top-[10vh] sm:rounded-[var(--radius-xl)] sm:p-7">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-[22px] font-semibold tracking-tight text-text-primary">
                {created ? 'Your link is ready' : 'Request files'}
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-[15px] text-text-secondary">
                {created ? 'Send it to your editor. You see the work once it is clean.' : 'Your editor gets a link to upload to. No account needed.'}
              </Dialog.Description>
            </div>
            <Dialog.Close className="press -mr-2 -mt-1 grid h-11 w-11 place-items-center rounded-full text-text-secondary hover:bg-bg-hover" aria-label="Close">
              <X className="h-5 w-5" />
            </Dialog.Close>
          </div>

          {created ? (
            <div className="mt-6 space-y-4 fade-in">
              <div className="flex items-center gap-2 rounded-[var(--radius-lg)] border border-border bg-bg-primary/50 p-2 pl-4">
                <Link2 className="h-4 w-4 shrink-0 text-text-tertiary" />
                <input readOnly value={created.url} onFocus={(e) => e.currentTarget.select()} aria-label="Request link"
                  className="min-w-0 flex-1 bg-transparent text-[15px] text-text-primary outline-none" />
                <button type="button" onClick={copy}
                  className={cn('press inline-flex h-11 items-center gap-2 rounded-full px-5 text-[15px] font-semibold',
                    copied ? 'bg-[rgba(48,209,88,0.14)] text-status-success' : 'bg-accent text-text-inverse hover:bg-accent-hover')}>
                  {copied ? <><Check className="h-4 w-4" /> Copied</> : <><Copy className="h-4 w-4" /> Copy</>}
                </button>
              </div>
              <p className="text-[13px] text-text-tertiary">
                Every upload is reviewed in about a minute. Must-fixes go back to the editor first; you will see it here as Ready.
              </p>
              <Dialog.Close className="press h-11 w-full rounded-full border border-border text-[15px] font-medium text-text-primary hover:bg-bg-hover">
                Done
              </Dialog.Close>
            </div>
          ) : (
            <form onSubmit={submit} className="mt-6 space-y-5">
              <Field label="Brand">
                {needsBrand ? (
                  <input ref={brandRef} value={newBrand} onChange={(e) => setNewBrand(e.target.value)} placeholder="e.g. Glow25"
                    className="field" aria-label="Brand name" />
                ) : (
                  <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="field" aria-label="Brand">
                    {brands.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                )}
              </Field>
              <Field label="What is it?">
                <input ref={titleRef} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. UraVia 48 · 3 hooks"
                  className="field" aria-label="Title" />
              </Field>
              <Field label="Briefing" hint="Optional. The review checks the cut against it.">
                {briefFile ? (
                  <div className="flex items-center gap-3 rounded-[var(--radius-lg)] border border-border bg-bg-primary/50 p-3 pl-4">
                    <FileText className="h-5 w-5 text-accent" />
                    <span className="min-w-0 flex-1 truncate text-[15px] text-text-primary">{briefFile.name}</span>
                    <button type="button" onClick={() => setBriefFile(null)} className="press grid h-9 w-9 place-items-center rounded-full text-text-tertiary hover:bg-bg-hover" aria-label="Remove briefing">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ) : pasting ? (
                  <textarea value={briefText} onChange={(e) => setBriefText(e.target.value)} rows={4} autoFocus
                    placeholder="Paste the script, or a Google Doc / Notion / Trello link"
                    className="field min-h-[112px] resize-y py-3 leading-relaxed" aria-label="Briefing text or link" />
                ) : (
                  <DropZone compact accept="application/pdf" onFiles={([f]) => setBriefFile(f)} title="Drop the briefing PDF" hint="or click to choose" />
                )}
                {!briefFile && (
                  <button type="button" onClick={() => setPasting((v) => !v)} className="mt-2 text-[13px] font-medium text-accent hover:underline">
                    {pasting ? 'Drop a PDF instead' : 'Paste text or a link instead'}
                  </button>
                )}
              </Field>
              {error && <p className="text-[13px] text-status-error" role="alert">{error}</p>}
              <button type="submit" disabled={!canSubmit}
                className="press h-12 w-full rounded-full bg-accent text-[17px] font-semibold text-text-inverse hover:bg-accent-hover disabled:bg-bg-hover disabled:text-text-tertiary">
                {busy ? 'Creating…' : 'Create link'}
              </button>
            </form>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <span className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="text-[15px] font-medium text-text-primary">{label}</span>
        {hint && <span className="text-[13px] text-text-tertiary">{hint}</span>}
      </span>
      {children}
    </div>
  )
}
