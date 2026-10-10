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
import * as Select from '@radix-ui/react-select'
import useSWR from 'swr'
import { Check, ChevronDown, FileText, X } from 'lucide-react'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth-store'
import { partsEnabled } from '@/lib/iterations'
import { createRequest, type FileRequest } from '@/lib/platform'
import type { Project } from '@/types'
import { BRIEFING_ACCEPT, briefingFilePayload } from '@/lib/briefing'
import { useBriefTitle } from '@/hooks/use-brief-title'
import { DropZone } from './drop-zone'
import { LinkCard } from './link-card'

export function RequestSheet({ open, onOpenChange, onCreated, initialProjectId }: {
  open: boolean
  onOpenChange: (v: boolean) => void
  onCreated?: (r: FileRequest) => void
  initialProjectId?: string
}) {
  const user = useAuthStore((s) => s.user)
  const isCustomer = user?.is_staff === false
  const { data: projects, mutate } = useSWR<Project[]>(open ? '/projects' : null, (k: string) => api.get<Project[]>(k))
  // Staff file into brand workspaces; a customer's own projects are all theirs.
  const brands = React.useMemo(
    () => (projects || []).filter((p) => isCustomer || p.is_workspace).sort((a, b) => a.name.localeCompare(b.name)),
    [projects, isCustomer],
  )

  const [projectId, setProjectId] = React.useState(initialProjectId || '')
  const [newBrand, setNewBrand] = React.useState('')
  const [title, setTitle] = React.useState('')
  const [briefFile, setBriefFile] = React.useState<File | null>(null)
  const [briefText, setBriefText] = React.useState('')
  const { edit: editTitle, reset: resetTitle } = useBriefTitle(briefFile, briefText, setTitle)
  const [receiveParts, setReceiveParts] = React.useState(partsEnabled)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState('')
  const [created, setCreated] = React.useState<FileRequest | null>(null)
  const createIdentity = React.useRef<{ payload: string; key: string } | null>(null)
  const sheetRef = React.useRef<HTMLDivElement>(null)
  React.useEffect(() => { if (created) sheetRef.current?.scrollTo({ top: 0 }) }, [created])
  const titleRef = React.useRef<HTMLInputElement>(null)
  const brandRef = React.useRef<HTMLInputElement>(null)

  // Sensible default (the only brand, or the first) - and a fresh form every time it opens.
  React.useEffect(() => {
    if (!open) return
    createIdentity.current = null
    resetTitle(); setCreated(null); setTitle(''); setBriefFile(null); setBriefText(''); setError('')
    if (initialProjectId) setProjectId(initialProjectId)
  }, [open, initialProjectId, resetTitle])
  React.useEffect(() => {
    if (brands.length && !brands.some((brand) => brand.id === projectId)) setProjectId(brands[0].id)
  }, [brands, projectId])
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
      const text = briefText.trim()
      const file = briefFile ? await briefingFilePayload(briefFile) : {}
      const isUrl = /^https?:\/\//i.test(text)
      let pid = projectId
      if (needsBrand) {
        const p = await api.post<Project>('/projects', { name: newBrand.trim(), project_type: 'team', is_workspace: true })
        pid = p.id
        await mutate()
      }
      const payload = {
        project_id: pid,
        ...(partsEnabled ? { receive_iterations: receiveParts } : {}),
        title: title.trim(),
        brief_text: [file.text, isUrl ? '' : text].filter(Boolean).join('\n\n'),
        brief_url: isUrl ? text : '',
        brief_pdf_base64: file.pdf_base64 || '',
        ...(file.docx_base64 ? { brief_docx_base64: file.docx_base64 } : {}),
      }
      const fingerprint = JSON.stringify(payload)
      if (createIdentity.current?.payload !== fingerprint) createIdentity.current = { payload: fingerprint, key: crypto.randomUUID() }
      const r = await createRequest({ ...payload, idempotency_key: createIdentity.current.key })
      setCreated(r)
      onCreated?.(r)
    } catch (err) {
      // Keep everything they typed; say what to do (Postel).
      setError(err instanceof Error ? err.message : 'That did not work. Try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-[2px] fade-in" />
        <Dialog.Content
          ref={sheetRef}
          // Focus the first thing to TYPE, not the first thing to tab to (the brand picker is prefilled).
          onOpenAutoFocus={(e) => e.preventDefault()}
          className="owner-sheet glass sheet-in fixed inset-x-0 bottom-0 z-50 mx-auto max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-b-none p-6 outline-none sm:bottom-auto sm:top-[10vh] sm:max-h-[80vh] sm:rounded-[var(--radius-xl)] sm:p-7">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-[22px] font-semibold tracking-tight text-text-primary">
                {created ? 'Your link is ready' : 'Request files'}
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-[15px] text-text-secondary">
                {created ? 'Ready to share with your editor.' : 'One upload link. No editor account needed.'}
              </Dialog.Description>
            </div>
            <Dialog.Close className="press -mr-2 -mt-1 grid h-11 w-11 place-items-center rounded-full text-text-secondary hover:bg-bg-hover" aria-label="Close">
              <X className="h-5 w-5" />
            </Dialog.Close>
          </div>

          {created ? (
            <div className="mt-6 space-y-4 fade-in">
              <LinkCard url={created.url} />
              <p className="text-[13px] text-text-tertiary">
                Share this link with your editor. They enter their name and email before uploading and appear in your leaderboard after their first upload.
              </p>
              <Dialog.Close className="press h-11 w-full rounded-full border border-border text-[15px] font-medium text-text-primary hover:bg-bg-hover">
                Done
              </Dialog.Close>
            </div>
          ) : (
            <form onSubmit={submit} className="mt-6 space-y-5">
              {brands.length === 1 ? <p className="text-[15px] text-text-secondary break-words">For <span className="font-medium text-text-primary">{brands[0].name}</span></p> : <Field label="Brand">
                {needsBrand ? (
                  <input ref={brandRef} value={newBrand} onChange={(e) => setNewBrand(e.target.value)} placeholder="e.g. Glow25"
                    className="field" aria-label="Brand name" />
                ) : (
                  <Select.Root value={projectId} onValueChange={setProjectId} disabled={busy || !brands.length}>
                    <Select.Trigger aria-label="Brand" className="field flex items-center justify-between gap-3 text-left"><Select.Value placeholder="Loading brands…" /><Select.Icon><ChevronDown size={16} className="text-text-secondary" /></Select.Icon></Select.Trigger>
                    <Select.Portal><Select.Content position="popper" sideOffset={6} className="owner-sheet z-[60] max-h-64 min-w-[var(--radix-select-trigger-width)] overflow-y-auto rounded-2xl border border-border bg-bg-elevated p-1.5 shadow-xl"><Select.Viewport>{brands.map(p => <Select.Item key={p.id} value={p.id} className="relative flex min-h-11 cursor-pointer items-center gap-3 rounded-xl py-2 pl-3 pr-10 text-[0.9375rem] outline-none data-[highlighted]:bg-accent-muted data-[highlighted]:text-accent"><Select.ItemText>{p.name}</Select.ItemText><Select.ItemIndicator className="absolute right-3"><Check size={16} /></Select.ItemIndicator></Select.Item>)}</Select.Viewport></Select.Content></Select.Portal>
                  </Select.Root>
                )}
              </Field>}
              <Field label="Project name">
                <input ref={titleRef} value={title} onChange={(e) => { editTitle(); setTitle(e.target.value) }} placeholder="e.g. UraVia 48 · 3 hooks"
                  className="field" aria-label="Title" />
              </Field>
              {partsEnabled && <Field label="Submission format"><div className="flex gap-2">{[true, false].map(value => <button key={String(value)} type="button" disabled={busy} aria-pressed={receiveParts === value} onClick={() => setReceiveParts(value)} className={`press min-h-11 rounded-full px-4 text-sm ${receiveParts === value ? 'bg-bg-hover font-medium' : 'text-text-secondary'}`}>{value ? 'Hooks & bodies' : 'Complete ads'}</button>)}</div><p className="mt-2 text-sm text-text-secondary">{receiveParts ? 'Your editor uploads each part once. We create and check the final combinations.' : 'Your editor uploads finished cuts for review.'}</p></Field>}
              <Field label="Briefing" hint="Optional">
                {briefFile ? (
                  <div className="flex items-center gap-3 rounded-[var(--radius-lg)] border border-border bg-bg-primary/50 p-3 pl-4">
                    <FileText className="h-5 w-5 text-accent" />
                    <span className="min-w-0 flex-1 truncate text-[15px] text-text-primary">{briefFile.name}</span>
                    <button type="button" onClick={() => setBriefFile(null)} className="press grid h-11 w-11 place-items-center rounded-full text-text-tertiary hover:bg-bg-hover" aria-label="Remove briefing">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ) : (
                  <DropZone compact disabled={busy} accept={BRIEFING_ACCEPT} onFiles={([f]) => { setBriefFile(f); setError('') }} title="Drop a briefing" hint="Word (.docx), PDF, Markdown or text · up to 10 MB" />
                )}
                <textarea value={briefText} onChange={(e) => setBriefText(e.target.value)} rows={2} disabled={busy}
                  placeholder="Paste a Google Docs link, another link, or your briefing…"
                  className="field mt-3 min-h-[88px] resize-y py-3 leading-relaxed" aria-label="Briefing text or link" />
                <p className="mt-2 text-[0.75rem] text-text-secondary">For links, enable access for anyone with the link.</p>
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
