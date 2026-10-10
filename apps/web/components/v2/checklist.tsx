'use client'
import useSWR from 'swr'
import { useEffect, useState } from 'react'
import { ApiError } from '@/lib/api'
import { getChecklist, prepareChecklist, retryChecklist, checklistPollInterval, type ChecklistState } from '@/lib/checklist'

/** SWR keys isolate A/B responses and deduplicate paste/blur for the same project/card.
 * A missing/ambiguous workspace leaves preparation dormant until the existing picker resolves it. */
export function useChecklistPreparation(projectId: string | null, url: string) {
  const card = url.trim().match(/^https:\/\/(?:www\.)?trello\.com\/c\/([A-Za-z0-9]+)(?:[/?#]|$)/)?.[1]
  const key = projectId && card ? `${projectId}/${card}` : null
  const [conflict, setConflict] = useState<{ key: string; error: ApiError } | null>(null)
  const result = useSWR<ChecklistState>(projectId && card ? ['prepare-checklist', projectId, card] : null,
    ([, project, id]: [string, string, string]) => prepareChecklist(project, `https://trello.com/c/${id}`),
    { revalidateOnFocus: false, revalidateOnReconnect: false, shouldRetryOnError: false, dedupingInterval: 10_000, keepPreviousData: false })
  const currentConflict = result.error && result.error instanceof ApiError && result.error.status === 409 ? result.error : null
  useEffect(() => {
    if (key && currentConflict) setConflict({ key, error: currentConflict })
    else if (result.data && !result.error) setConflict(null)
    else setConflict(previous => previous?.key === key ? previous : null)
  }, [key, currentConflict, result.data, result.error])
  return { ...result, conflict: currentConflict || (conflict?.key === key ? conflict.error : null),
    rememberConflict: (error: ApiError) => { if (key) setConflict({ key, error }) } }
}

export function SavedChecklist({ bindingId, initial }: { bindingId?: string | null; initial?: ChecklistState | null }) {
  const [retryError, setRetryError] = useState<{ bindingId: string; message: string } | null>(null)
  const { data, error, mutate } = useSWR(bindingId ? ['saved-checklist', bindingId] : null,
    () => getChecklist(bindingId!), { fallbackData: initial || undefined, refreshInterval: checklistPollInterval,
      revalidateOnFocus: false, shouldRetryOnError: false, keepPreviousData: false })
  if (!bindingId) return null
  return <ChecklistPanel data={data} error={(retryError?.bindingId === bindingId ? retryError.message : undefined) || (error ? 'The checklist could not be loaded.' : undefined)} onRetry={async () => {
    setRetryError(null)
    try {
      if (data?.status === 'failed') await mutate(await retryChecklist(bindingId), false)
      else await mutate()
    } catch { setRetryError({ bindingId, message: 'The checklist could not be retried. Try again.' }) }
  }} />
}

const labels = { basics: 'Basics', brand: 'Brand', briefing: 'Briefing' }
const reasons: Record<string, string> = {
  'plan-api-unavailable': 'Checklist preparation is not available yet.',
  'review-unconfigured': 'Checklist preparation is not connected yet.',
  'briefing-unavailable': 'The saved briefing could not be read. If it uses a document link, check sharing permissions (anyone with the link), then try again.',
  'plan-conflict': 'This assignment has conflicting checklist data.',
  'snapshot-identity-invalid': 'The checklist could not be matched to this assignment.',
}
export function ChecklistPanel({ data, error, onRetry, uploadAllowed = true }: { data?: ChecklistState; error?: string; onRetry?: () => void | Promise<unknown>; uploadAllowed?: boolean }) {
  const failed = !!error || data?.status === 'failed' || (data?.status === 'ready' && !data.requirements.length)
  const ready = !failed && data?.status === 'ready'
  return <section aria-label='Review checklist' className='min-w-0 rounded-xl border border-border bg-bg-secondary p-4 text-base leading-relaxed text-text-primary'>
    {failed ? <div>
      <p role='status'>Checklist unavailable.{uploadAllowed ? ' You can still upload.' : ''}</p>
      <p className='mt-1 text-sm text-text-secondary'>{error || reasons[data?.error_code || ''] || 'The saved checklist could not be prepared.'}</p>
      {onRetry && <button type='button' className='press mt-2 min-h-11 cursor-pointer rounded-lg px-3 text-sm font-medium text-text-primary hover:bg-bg-hover focus-visible:ring-2 focus-visible:ring-accent' onClick={() => void onRetry()}>Try again</button>}
    </div> : ready ? <details>
      <summary className='min-h-11 w-full cursor-pointer py-2 font-medium focus-visible:rounded-md focus-visible:ring-2 focus-visible:ring-accent'>{data.requirements.length} review {data.requirements.length === 1 ? 'check' : 'checks'}</summary>
      <p className='mt-2 text-sm text-text-secondary'>Same checks for every version.</p>
      <ol className='mt-4 space-y-4'>
        {data.requirements.map(r => <li key={r.id} className='min-w-0 border-t border-border pt-3'>
          <p className='break-words'>{r.text}</p>
          <div className='mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm text-text-secondary'>
            {r.sources.length ? Array.from(new Set(r.sources.map(s => s.layer))).map(layer => <span key={layer}>{labels[layer] || 'Source unavailable'}</span>) : <span>Source unavailable</span>}
            <span>{({ video: 'Per video', variant: 'Per variant', submission: 'Whole submission' } as Record<string,string>)[r.applicability] || 'Scope unclear'}</span>
          </div>
        </li>)}
      </ol>
      {data.limitations.length > 0 && <p className='mt-4 text-sm text-text-secondary'>Some requirements need clarification. Preparation does not confirm that a video meets these checks.</p>}
    </details> : <p role='status' aria-live='polite'>Preparing review checklist…</p>}
  </section>
}
