import { api } from './api'
import { pub, type ReviewComment } from './platform'

export const partsEnabled = process.env.NEXT_PUBLIC_HANDIN_COMPONENTS_ENABLED === 'true'
export type PartRole = 'hook' | 'opening' | 'lead' | 'body' | 'cta'
export interface IterationSlot { id: string; label: string; role: PartRole; group: string; script: string }
export interface IterationManifest { schema_version: number; summary: string; slots: IterationSlot[]; recipes: { id: string; label: string; slots: string[] }[] }
export interface IterationMedia {
  bytes_stored?: boolean
  asset_id?: string; version_id?: string; version_number?: number; duration_seconds?: number
  versions?: { id: string; version_number: number; processing: string }[]
  media_url?: string; thumbnail_url?: string | null; status: string; findings: ReviewComment[]; error?: string
}
export interface IterationProgress {
  enabled: boolean; mode: 'complete' | 'components'; manifest: IterationManifest
  slots: (IterationMedia & { slot_id: string })[]
  outputs: (IterationMedia & { id: string; recipe_id?: string; slot_ids?: string[]; label: string; download_url?: string; review_url?: string })[]
  state: string; delivered: number; total: number; submitted: boolean; can_leave: boolean; editor_done: boolean; error?: string
  simple?: boolean
}
export const requestIterations = (token: string) => pub<IterationProgress>('GET', `/r/${token}/iterations`)
export const declareParts = (token: string, parts: { id: string; role: PartRole; label: string }[]) => pub<IterationProgress>('POST', `/r/${token}/iterations/parts`, { parts })
export const removePart = (token: string, id: string) => pub<IterationProgress>('DELETE', `/r/${token}/iterations/parts/${encodeURIComponent(id)}`)
export const submitParts = (token: string) => pub<IterationProgress>('POST', `/r/${token}/iterations/submit`, {})
export const retryParts = (token: string) => pub<IterationProgress>('POST', `/r/${token}/iterations/retry`, {})
export const setSubmissionMode = (token: string, mode: 'complete' | 'components') => pub<IterationProgress>('POST', `/r/${token}/submission-mode`, { mode })
export const objectToOutputNote = (token: string, id: string, body: { comment_id?: string; body: string; text: string; who?: string }) => pub<{ withdrawn: boolean; why: string }>('POST', `/r/${token}/iterations/outputs/${encodeURIComponent(id)}/object`, body)
export const createPartHandin = (project_id: string, card_url: string) => api.post<{ token: string; url?: string; upload_url?: string }>('/handins', { project_id, card_url })
export interface PrivatePart { id: string; source_id: string; version_id: string; role: PartRole; name: string; size_bytes: number; created_at: number }
export const listPrivateParts = (projectId: string) => api.get<{ parts: PrivatePart[] }>(`/projects/${projectId}/iteration-parts`)

/** The server owns completion. A loaded progress object never turns pending work green locally. */
export function handoffMessage(p: IterationProgress, transferring: boolean) {
  if (transferring) return { title: 'Uploading your parts', detail: 'Keep this tab open until all files are saved.' }
  if (!p.submitted) return { title: 'Ready when you are', detail: 'Add all your parts, then submit. Finished uploads can already be checked.' }
  if (p.state === 'held') return { title: 'A part needs your attention', detail: 'Open the feedback below and replace only the affected part.' }
  if (p.state === 'error') return { title: 'We need to retry a step', detail: 'Your saved files are safe. This does not mean your edit failed the review.' }
  if (p.state === 'delivered' && p.total > 0 && p.delivered === p.total) return { title: `${p.total} ${p.total === 1 ? 'ad' : 'ads'} delivered`, detail: 'The final files passed review and are ready below.' }
  if (p.editor_done) return { title: 'Your part is done', detail: 'We’re creating and checking the final ads. You can close this tab and return to this link later.' }
  if (p.can_leave) return { title: 'Submitted · checking your parts', detail: 'Your files are saved. You can close this tab; return to this link to see feedback.' }
  return { title: 'Confirming your submission', detail: 'Keep this tab open while we confirm that your files are saved.' }
}
