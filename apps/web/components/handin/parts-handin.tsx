'use client'
import * as React from 'react'
import useSWR from 'swr'
import { ArrowRight, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import { viewRequest } from '@/lib/platform'
import { createPartHandin } from '@/lib/iterations'
import { useAuthStore } from '@/stores/auth-store'
import { WorkspacePicker, type WorkspaceChoice } from './workspace-picker'
import { PartsWorkspace } from '@/components/v2/parts-workspace'
import type { Project } from '@/types'

export function PartsHandin({ onStarted }: { onStarted?: () => void }) {
  const user = useAuthStore(s => s.user)
  const { data: projects } = useSWR<Project[]>('/projects', () => api.get<Project[]>('/projects'))
  const [workspace, setWorkspace] = React.useState<WorkspaceChoice | null>(null)
  const [cardUrl, setCardUrl] = React.useState('')
  const [token, setToken] = React.useState('')
  const { data: requestView } = useSWR(token ? `/r/${token}` : null, () => viewRequest(token))
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState('')
  React.useEffect(() => { const saved = new URLSearchParams(window.location.search).get('submission'); if (saved) { setToken(saved); onStarted?.() } }, [onStarted])
  const options = (projects || []).filter(p => (p.is_workspace || user?.is_staff === false) && (p.role === 'owner' || p.role === 'editor' || user?.is_superadmin)).map(p => ({ id: p.id, name: p.name }))
  const open = async (e: React.FormEvent) => {
    e.preventDefault()
    if (workspace?.kind !== 'existing' || busy) return
    setBusy(true); setError('')
    try {
      const request = await createPartHandin(workspace.id, cardUrl.trim())
      setToken(request.token); onStarted?.()
      const url = new URL(window.location.href); url.searchParams.set('submission', request.token)
      window.history.replaceState(null, '', url)
    } catch (e) { setError(e instanceof Error ? e.message : 'This hand-in could not be opened. Please retry.') }
    finally { setBusy(false) }
  }
  return <div className="mx-auto max-w-[1040px] px-5 pb-28 pt-8 sm:px-8 sm:pt-10">
    <div className={`mb-8 ${token ? '' : 'mx-auto max-w-2xl text-center'}`}><p className="mb-3 text-sm text-text-secondary">Editor workspace</p><h1 className={token ? 'text-[1.75rem] font-semibold leading-tight tracking-tight' : 'text-[2.125rem] font-bold leading-[1.1] tracking-[-0.02em] sm:text-[2.5rem]'}>Hand in</h1><p className={`mt-4 max-w-xl text-base leading-relaxed text-text-secondary ${token ? '' : 'mx-auto'}`}>Upload your hooks and bodies once. Get feedback here while we take care of the final ads.</p></div>
    {token ? <><p className="mb-5 text-sm text-text-secondary"><span className="font-medium text-text-primary">{requestView?.brand || workspace?.name}</span>{requestView?.title && <> · {requestView.title}</>}<span className="mt-2 block">Keep this link to return to your submission.</span></p><PartsWorkspace token={token} brand={requestView?.brand || workspace?.name} who={user ? { name: user.name, email: user.email } : undefined} /></> : <form onSubmit={open} className="mx-auto max-w-2xl space-y-6 rounded-[var(--radius-xl)] border border-border bg-bg-secondary p-6 sm:p-8">
      <div><label htmlFor="parts-card" className="text-sm font-medium">Trello card</label><input id="parts-card" type="url" required value={cardUrl} onChange={e => setCardUrl(e.target.value)} placeholder="https://trello.com/c/…" className="field mt-2 w-full" /><p className="mt-2 text-sm text-text-secondary">The card supplies the brief and receives the finished ads.</p></div>
      <div><label className="text-sm font-medium">Workspace</label><div className="mt-2"><WorkspacePicker projects={options} value={workspace} onChange={setWorkspace} allowCreate={false} /></div><p className="mt-2 text-sm text-text-secondary">Parts and final ads will belong to this workspace.</p></div>
      {error && <p role="alert" className="text-sm text-status-error">{error}</p>}
      <button disabled={busy || workspace?.kind !== 'existing' || !cardUrl.trim()} className="press inline-flex min-h-11 items-center gap-2 rounded-full bg-accent px-6 text-sm font-semibold text-text-inverse disabled:opacity-40">{busy ? <Loader2 size={17} className="animate-spin" /> : <ArrowRight size={17} />}{busy ? 'Opening submission…' : 'Continue to upload'}</button>
    </form>}
  </div>
}
