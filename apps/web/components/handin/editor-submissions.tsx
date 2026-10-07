'use client'
import Link from 'next/link'
import useSWR from 'swr'
import { listRequests, statusLabel } from '@/lib/platform'

export function EditorSubmissions() {
  const { data, error, mutate } = useSWR('/requests', listRequests, { refreshInterval: 15000 })
  return <div className="handin-workspace mx-auto max-w-[1040px] px-5 pb-28 pt-8 sm:px-8"><div className="flex flex-wrap items-center justify-between gap-4"><h1 className="text-[1.75rem] font-semibold tracking-tight">Submissions</h1><Link href="/handin" className="press inline-flex min-h-11 items-center rounded-full bg-accent px-5 text-sm font-semibold text-text-inverse">New hand-in</Link></div><p className="mt-3 text-base text-text-secondary">Return to feedback and files in your workspaces.</p>
    {error ? <p role="alert" className="mt-6 text-sm text-status-error">Submissions could not be loaded. <button className="min-h-11 underline" onClick={() => mutate()}>Retry</button></p> : !data ? <p role="status" className="mt-6 text-text-secondary">Loading submissions…</p> : !data.length ? <p className="mt-6 text-text-secondary">Your hand-ins will appear here.</p> : <ul className="mt-6 divide-y divide-border">{data.filter(r => r.state === 'live').map(request => <li key={request.id}><Link href={`/r/${request.token}`} className="flex min-h-20 items-center justify-between gap-4 py-4"><div><p className="font-medium">{request.title}</p><p className="mt-1 text-sm text-text-secondary">{request.project_name}</p></div><span className="text-sm text-text-secondary">{statusLabel(request).label}</span></Link></li>)}</ul>}
  </div>
}
