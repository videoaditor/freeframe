'use client'
import * as React from 'react'
import useSWR from 'swr'
import { Download, FileVideo } from 'lucide-react'
import { api } from '@/lib/api'
import { authHeaders } from '@/lib/auth-headers'
import { getAccessToken, refreshAccessToken } from '@/lib/auth'
import { listPrivateParts, type PrivatePart } from '@/lib/iterations'
import { ownsProject } from '@/lib/workspace-access'
import { useAuthStore } from '@/stores/auth-store'
import { formatBytes } from '@/lib/platform'
import type { Project } from '@/types'

export default function PartsPage() {
  const user = useAuthStore(s => s.user)
  const { data: projects } = useSWR<Project[]>('/projects', () => api.get<Project[]>('/projects'))
  const owners = (projects || []).filter(p => ownsProject(user, p))
  const [selected, setSelected] = React.useState('')
  const project = owners.find(p => p.id === selected) || owners[0]
  const { data, error, mutate } = useSWR(project ? ['private-parts', project.id] : null, () => listPrivateParts(project!.id))
  const [downloading, setDownloading] = React.useState('')
  const [failure, setFailure] = React.useState('')
  const download = async (part: PrivatePart) => {
    if (!project) return
    setDownloading(part.id); setFailure('')
    try {
      const url = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/projects/${project.id}/iteration-parts/${encodeURIComponent(part.id)}/file`
      let token = getAccessToken()
      let response = await fetch(url, { headers: authHeaders(token) })
      if (response.status === 401) { token = await refreshAccessToken(token); if (token) response = await fetch(url, { headers: authHeaders(token) }) }
      if (!response.ok) throw new Error('This original could not be downloaded. Please retry.')
      const href = URL.createObjectURL(await response.blob())
      const a = document.createElement('a'); a.href = href; a.download = part.name; a.click()
      setTimeout(() => URL.revokeObjectURL(href), 30000)
    } catch (e) { setFailure(e instanceof Error ? e.message : 'Please retry.') }
    finally { setDownloading('') }
  }
  return <div className="owner-workspace handin-workspace mx-auto max-w-[1040px] px-5 pb-28 pt-8 sm:px-8"><h1 className="text-[1.75rem] font-semibold tracking-tight">Reusable parts</h1><p className="mt-3 max-w-xl text-base leading-relaxed text-text-secondary">Original hooks and bodies from your assembled ads. Private to your workspace, ready to download for the next edit.</p>
    {project && <label className="mt-6 block text-sm font-medium">Workspace<select value={project.id} onChange={e => setSelected(e.target.value)} className="field mt-2 block max-w-full">{owners.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>}
    {error || failure ? <p role="alert" className="mt-6 text-sm text-status-error">{failure || 'Your parts could not be loaded.'}<button className="ml-3 min-h-11 underline" onClick={() => { setFailure(''); mutate() }}>Retry</button></p> : !projects || (project && !data) ? <p role="status" className="mt-8 text-text-secondary">Loading your parts…</p> : !project ? <p className="mt-8 text-text-secondary">Reusable parts are available to workspace owners.</p> : !data?.parts.length ? <p className="mt-8 rounded-2xl bg-bg-secondary p-6 text-text-secondary">Your originals appear here after the first set of parts is prepared for assembly.</p> : <ul className="mt-6 divide-y divide-border">{data.parts.map(part => <li key={part.id} className="flex items-center gap-4 py-4"><FileVideo size={22} className="shrink-0 text-text-secondary" /><div className="min-w-0 flex-1"><p className="break-words font-medium">{part.name}</p><p className="mt-1 text-sm text-text-secondary">{part.role === 'lead' ? 'Bridge' : part.role} · {formatBytes(part.size_bytes)}</p></div><button disabled={!!downloading} className="press inline-flex min-h-11 items-center gap-2 rounded-full px-4 text-sm font-medium text-accent disabled:opacity-50" onClick={() => download(part)}><Download size={16} />{downloading === part.id ? 'Downloading…' : 'Download'}</button></li>)}</ul>}
  </div>
}
