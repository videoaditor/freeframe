'use client'

/**
 * Home (platform v2). The owner's one question: what came back? One dominant action - Request
 * files - and the list of requests with where each one stands, in words.
 */
import * as React from 'react'
import Link from 'next/link'
import useSWR from 'swr'
import { ArrowUpRight, Check, Copy, Plus, Timer, BookOpen } from 'lucide-react'
import { useAuthStore } from '@/stores/auth-store'
import { usePageTitle } from '@/hooks/use-page-title'
import { getTimeSaved, hours, listRequests, statusLabel, type FileRequest } from '@/lib/platform'
import { RequestSheet } from '@/components/v2/request-sheet'
import { StatusPill } from '@/components/v2/status-pill'
import { FolderArt } from '@/components/v2/folder-art'
import { cn } from '@/lib/utils'

function greeting(): string {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

export default function HomePage() {
  usePageTitle('Home')
  const user = useAuthStore((s) => s.user)
  const [sheet, setSheet] = React.useState(false)
  // Poll while anything is still being reviewed or fixed, so "Ready" appears without a reload.
  const { data: requests, mutate, isLoading } = useSWR<FileRequest[]>('/requests', listRequests, {
    refreshInterval: (d) => (d || []).some((r) => r.status !== 'clear' && r.assets > 0) ? 8000 : 30000,
  })
  const { data: saved } = useSWR('/insights/time-saved?30', () => getTimeSaved(30), { shouldRetryOnError: false })
  const first = user?.name?.split(' ')[0]

  return (
    <div className="page-in mx-auto w-full max-w-5xl px-4 pb-20 pt-8 sm:px-8 sm:pt-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[15px] text-text-secondary">{greeting()}{first ? `, ${first}` : ''}</p>
          <h1 className="mt-1 text-[34px] font-bold leading-tight tracking-[-0.02em] text-text-primary">Your requests</h1>
        </div>
        <button type="button" onClick={() => setSheet(true)}
          className="press inline-flex h-12 items-center gap-2 rounded-full bg-accent px-6 text-[17px] font-semibold text-text-inverse hover:bg-accent-hover">
          <Plus className="h-5 w-5" strokeWidth={2.25} /> Request files
        </button>
      </div>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <Link href="/insights" className="press glass group flex items-center gap-4 p-5">
          <span className="grid h-11 w-11 place-items-center rounded-full bg-accent-muted text-accent"><Timer className="h-5 w-5" /></span>
          <span className="min-w-0 flex-1">
            <span className="block text-[13px] text-text-secondary">Saved in the last 30 days</span>
            <span className="block text-[22px] font-semibold tabular-nums tracking-tight text-text-primary">
              {saved ? `${hours(saved.totalSec)} hours` : '—'}
            </span>
          </span>
          <ArrowUpRight className="h-5 w-5 text-text-tertiary transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
        </Link>
        <Link href="/rules" className="press glass group flex items-center gap-4 p-5">
          <span className="grid h-11 w-11 place-items-center rounded-full bg-bg-hover text-text-primary"><BookOpen className="h-5 w-5" /></span>
          <span className="min-w-0 flex-1">
            <span className="block text-[13px] text-text-secondary">What the reviewer checks</span>
            <span className="block text-[22px] font-semibold tracking-tight text-text-primary">Brand rules</span>
          </span>
          <ArrowUpRight className="h-5 w-5 text-text-tertiary transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
        </Link>
      </div>

      <section className="mt-10" aria-label="Requests">
        {isLoading ? (
          <div className="space-y-2">{[0, 1, 2].map((i) => <div key={i} className="skeleton-shimmer h-[76px] animate-shimmer rounded-[var(--radius-lg)]" />)}</div>
        ) : !requests?.length ? (
          <button type="button" onClick={() => setSheet(true)}
            className="press flex w-full flex-col items-center gap-4 rounded-[var(--radius-xl)] border border-dashed border-border bg-bg-secondary/50 px-6 py-14 text-center hover:border-accent">
            <FolderArt size={96} />
            <span className="text-[20px] font-semibold tracking-tight text-text-primary">Request your first files</span>
            <span className="max-w-sm text-[15px] text-text-secondary">Drop a briefing, get a link, send it to your editor. You only see the work once it is clean.</span>
          </button>
        ) : (
          <ul className="stagger space-y-2">
            {requests.map((r) => <RequestRow key={r.id} r={r} />)}
          </ul>
        )}
      </section>

      <RequestSheet open={sheet} onOpenChange={setSheet} onCreated={() => mutate()} />
    </div>
  )
}

function RequestRow({ r }: { r: FileRequest }) {
  const [copied, setCopied] = React.useState(false)
  const s = statusLabel(r)
  const ready = s.tone === 'ok'
  const copy = async () => {
    await navigator.clipboard.writeText(r.url).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }
  const body = (
    <>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[17px] font-semibold tracking-tight text-text-primary">{r.title}</span>
        <span className="mt-0.5 block truncate text-[13px] text-text-secondary">
          {r.project_name}
          {r.assets ? ` · ${r.assets} ${r.assets === 1 ? 'file' : 'files'}` : ''}
          {r.last_uploader_name ? ` · from ${r.last_uploader_name}` : ''}
        </span>
      </span>
      <StatusPill label={s.label} tone={s.tone} />
    </>
  )
  return (
    <li className="flex items-center gap-2 rounded-[var(--radius-lg)] border border-border bg-bg-secondary pr-2 transition-colors hover:bg-bg-tertiary">
      {ready ? (
        // Ready opens the hand-in. Not-ready is not a link: the owner waits, the editor fixes.
        <Link href={`/projects/${r.project_id}`} className="flex min-w-0 flex-1 items-center gap-4 py-4 pl-5">{body}</Link>
      ) : (
        <div className="flex min-w-0 flex-1 items-center gap-4 py-4 pl-5">{body}</div>
      )}
      <button type="button" onClick={copy} aria-label="Copy request link" title="Copy request link"
        className={cn('press grid h-11 w-11 shrink-0 place-items-center rounded-full', copied ? 'text-status-success' : 'text-text-tertiary hover:bg-bg-hover hover:text-text-primary')}>
        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </button>
    </li>
  )
}
