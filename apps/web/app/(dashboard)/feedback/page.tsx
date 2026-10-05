'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { api, ApiError } from '@/lib/api'
import { Button } from '@/components/ui/button'

type Feedback = {
  id: string; author_id: string; campaign_id: string | null; tool: string
  kind: 'bug' | 'idea'; message: string; triage_status: string; created_at: string
}
type Queue = { items: Feedback[]; next_offset: number | null }

export default function FeedbackQueuePage() {
  const [offset, setOffset] = useState(0)
  const { data, error, isLoading, mutate } = useSWR<Queue>(`/product-feedback?offset=${offset}&limit=25`, (path: string) => api.get<Queue>(path))
  return (
    <main className="mx-auto w-full max-w-4xl space-y-6 p-4 sm:p-8">
      <div><h1 className="text-2xl font-semibold">Product feedback</h1><p className="mt-2 text-text-secondary">Customer reports for staff review. No automatic actions are taken.</p></div>
      {isLoading && <p role="status">Loading feedback…</p>}
      {error && <div role="alert" className="space-y-3"><p>{error instanceof ApiError && error.status === 403 ? 'Staff access required.' : 'Feedback could not be loaded.'}</p>{!(error instanceof ApiError && error.status === 403) && <Button variant="secondary" size="lg" onClick={() => mutate()}>Try again</Button>}</div>}
      {data && !error && <>
        {!data.items.length && <p className="text-text-secondary">No feedback yet.</p>}
        {data.items.map(item => <article id={item.id} key={item.id} className="space-y-3 rounded-xl border border-border bg-bg-secondary p-6">
          <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold">{item.kind === 'bug' ? 'Bug report' : 'Improvement idea'}</h2><time className="text-sm text-text-secondary" dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time></div>
          <p className="whitespace-pre-wrap break-words text-[1.0625rem] leading-6">{item.message}</p>
          <p className="break-words text-sm text-text-secondary">{item.tool} · {item.campaign_id || 'No campaign'} · {item.triage_status}</p>
          <p className="break-all text-xs text-text-secondary">Receipt: {item.id} · Author: {item.author_id}</p>
        </article>)}
        <div className="flex gap-3"><Button variant="secondary" size="lg" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>Previous</Button><Button variant="secondary" size="lg" disabled={data.next_offset === null} onClick={() => setOffset(data.next_offset!)}>Next</Button></div>
      </>}
    </main>
  )
}
