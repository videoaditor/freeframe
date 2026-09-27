/**
 * Platform v2 client: file requests, the anonymous try, rules and time saved.
 * Spec: docs/superpowers/specs/2026-09-28-review-platform-v2-design.md.
 *
 * Two backends:
 *   - FreeFrame's own API (`api`) for everything an owner or an editor-with-a-link does;
 *   - Auto Review (GATE_BASE, review.aditor.ai) ONLY for the anonymous try, straight from the
 *     browser - there is no account and no FreeFrame project behind it.
 */
import { api } from './api'
import { GATE_BASE } from './handin'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ── Types ──────────────────────────────────────────────────────────────────────

export type GateStatus = 'reviewing' | 'held' | 'clear'

export interface FileRequest {
  id: string
  token: string
  url: string
  title: string
  project_id: string
  project_name: string
  brief_excerpt: string | null
  last_uploader_name: string | null
  assets: number
  state: 'live' | 'revoked' | 'expired'
  status: GateStatus
  open_must_fixes: number
  created_at: string | null
}

export interface ReviewComment { id?: string; t: number | null; body: string; must_fix?: boolean; weight?: 'must_fix' | 'optional' }

export interface TimeSaved {
  days: number
  videos: number
  watchSec: number
  typeSec: number
  totalSec: number
  perDay: { day: string; sec: number }[]
  perBrand: { brand: string; sec: number; videos: number }[]
  assumptions: { wpm: number; watches: number }
}

// ── Pure helpers (tested) ──────────────────────────────────────────────────────

/** "0:07", "1:23", "1:02:05" - the timestamp chip on a comment. */
export function timecode(t: number | null | undefined): string {
  if (t === null || t === undefined || !Number.isFinite(t)) return ''
  const s = Math.max(0, Math.floor(t))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`
}

/** Big, human: "12 h 5 min", "48 min", "under a minute". */
export function humanDuration(sec: number): string {
  if (!Number.isFinite(sec) || sec < 60) return 'under a minute'
  const h = Math.floor(sec / 3600)
  const m = Math.round((sec % 3600) / 60)
  if (!h) return `${m} min`
  return m ? `${h} h ${m} min` : `${h} h`
}

/** Hours with one decimal for the hero number: 12.1 */
export function hours(sec: number): string {
  return (Math.max(0, sec) / 3600).toFixed(sec >= 36000 ? 0 : 1)
}

export function formatBytes(b: number): string {
  if (b < 1024 * 1024) return `${Math.max(1, Math.round(b / 1024))} KB`
  if (b < 1024 * 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)} MB`
  return `${(b / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

/** What the owner reads on a request row. One label, one tone - never a number without words. */
export function statusLabel(r: Pick<FileRequest, 'status' | 'open_must_fixes' | 'assets' | 'state'>): { label: string; tone: 'neutral' | 'progress' | 'warn' | 'ok' } {
  if (r.state !== 'live') return { label: r.state === 'revoked' ? 'Closed' : 'Expired', tone: 'neutral' }
  if (!r.assets) return { label: 'Waiting for files', tone: 'neutral' }
  if (r.status === 'reviewing') return { label: 'Reviewing', tone: 'progress' }
  if (r.status === 'held') {
    const n = r.open_must_fixes
    return { label: `Editor is fixing ${n} ${n === 1 ? 'thing' : 'things'}`, tone: 'warn' }
  }
  return { label: 'Ready', tone: 'ok' }
}

/** Split a file into the Worker's upload slices (under its ~100MB request cap). */
export const TRY_PART_BYTES = 16 * 1024 * 1024
export function sliceRanges(size: number, part = TRY_PART_BYTES): [number, number][] {
  const out: [number, number][] = []
  for (let start = 0; start < size; start += part) out.push([start, Math.min(size, start + part)])
  return out
}

/** Read a video's duration locally, before any byte leaves the machine. */
export function videoDuration(file: File): Promise<number> {
  return new Promise((resolve) => {
    const v = document.createElement('video')
    v.preload = 'metadata'
    const url = URL.createObjectURL(file)
    const done = (d: number) => { URL.revokeObjectURL(url); resolve(Number.isFinite(d) ? d : 0) }
    v.onloadedmetadata = () => done(v.duration)
    v.onerror = () => done(0)
    v.src = url
  })
}

// ── Anonymous try (browser → Auto Review) ──────────────────────────────────────

export class TryError extends Error {
  constructor(public code: string, message: string) { super(message) }
}

const TRY_MESSAGES: Record<string, string> = {
  'try-limit': 'That was today’s three free reviews. Continue with your email to keep going.',
  'too-big': 'That file is over 300 MB. Export a lighter version and drop it again.',
  'too-long': 'Free reviews are for ads up to 3 minutes. Continue with your email for longer videos.',
  'review-failed': 'The review did not come back this time. Drop the file again in a moment.',
}

export async function tryReview(
  file: File,
  onProgress: (fraction: number) => void,
): Promise<{ comments: ReviewComment[]; left: number }> {
  if (!GATE_BASE) throw new TryError('off', 'Free reviews are not switched on here.')
  const durationSec = await videoDuration(file)
  if (durationSec > 180) throw new TryError('too-long', TRY_MESSAGES['too-long'])
  if (file.size > 300 * 1024 * 1024) throw new TryError('too-big', TRY_MESSAGES['too-big'])
  const id = (crypto.randomUUID?.() || String(Date.now())).replace(/[^a-zA-Z0-9-]/g, '')
  const ranges = sliceRanges(file.size)
  let sent = 0
  for (let i = 0; i < ranges.length; i++) {
    const [a, b] = ranges[i]
    const r = await fetch(`${GATE_BASE}/api/v1/try/part?id=${id}&i=${i}`, { method: 'POST', body: file.slice(a, b) })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      throw new TryError(j.error || 'upload', TRY_MESSAGES[j.error] || 'The upload stopped. Drop the file again.')
    }
    sent += b - a
    onProgress(sent / file.size)
  }
  const r = await fetch(`${GATE_BASE}/api/v1/try`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ upload: id, parts: ranges.length, len: file.size, name: file.name, durationSec }),
  })
  const j = await r.json().catch(() => ({}))
  if (!r.ok) throw new TryError(j.error || 'review-failed', TRY_MESSAGES[j.error] || TRY_MESSAGES['review-failed'])
  return { comments: j.comments || [], left: j.left ?? 0 }
}

// ── Owner ──────────────────────────────────────────────────────────────────────

export const listRequests = () => api.get<FileRequest[]>('/requests')
export const createRequest = (body: { project_id: string; title: string; brief_text?: string; brief_url?: string; brief_pdf_base64?: string }) =>
  api.post<FileRequest>('/requests', body)
export const revokeRequest = (id: string) => api.delete(`/requests/${id}`)
export const getTimeSaved = (days = 30) => api.get<TimeSaved>(`/insights/time-saved?days=${days}`)
export const getRules = (projectId: string) => api.get<{ brand: string; rules: RuleRow[]; suggestions: SuggestionRow[] }>(`/insights/rules?project_id=${projectId}`)
export const importRules = (body: { project_id: string; text?: string; url?: string; pdf_base64?: string }) =>
  api.post<{ drafted: number; found: number }>('/insights/rules/import', body)

export const decideSuggestion = (body: { project_id: string; suggestion_id: string; action: 'accept' | 'dismiss' }) =>
  api.post<{ ok: boolean }>('/insights/rules/suggestion', body)

export interface RuleRow { id: string; name: string; what: string; scope: string; severity: string; active: boolean }
export interface SuggestionRow { id: string; name?: string; what?: string; source?: string }

export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(String(r.result).split(',')[1] || '')
    r.onerror = () => reject(r.error)
    r.readAsDataURL(file)
  })
}

// ── Editor with a link (no account) ────────────────────────────────────────────

export interface RequestView {
  title: string
  brand: string
  brief_excerpt: string | null
  review_share_token: string
  assets: { id: string; name: string }[]
  expires_at: string | null
}

export interface RequestReview {
  assets: { asset_id: string; name: string; version: number; processing: string; comments: ReviewComment[] }[]
  gate: { status: GateStatus; open_must_fixes: number }
  review_share_token: string
}

async function pub<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, {
    method,
    headers: body ? { 'content-type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) {
    const j = await r.json().catch(() => ({}))
    const detail = typeof j.detail === 'string' ? j.detail : 'Something went wrong. Try again.'
    throw Object.assign(new Error(detail), { status: r.status })
  }
  return r.status === 204 ? (undefined as T) : r.json()
}

export const viewRequest = (token: string) => pub<RequestView>('GET', `/r/${token}`)
export const requestReview = (token: string) => pub<RequestReview>('GET', `/r/${token}/review`)
export const objectToNote = (token: string, body: { asset_id: string; comment_id?: string; body: string; text: string; name?: string }) =>
  pub<{ withdrawn: boolean; why: string }>('POST', `/r/${token}/object`, body)

const CHUNK = 10 * 1024 * 1024

/** Multipart upload into the request's folder, the same presigned-part path a signed-in editor uses. */
export async function uploadToRequest(
  token: string,
  who: { name: string; email: string },
  file: File,
  onProgress: (fraction: number) => void,
): Promise<{ asset_id: string; version_number: number }> {
  const init = await pub<{ upload_id: string; s3_key: string; asset_id: string; version_id: string; version_number: number }>(
    'POST', `/r/${token}/upload/initiate`, {
      name: who.name, email: who.email, original_filename: file.name,
      mime_type: file.type || 'video/mp4', file_size_bytes: file.size,
    })
  const parts: { PartNumber: number; ETag: string }[] = []
  const total = Math.ceil(file.size / CHUNK)
  try {
    for (let n = 1; n <= total; n++) {
      const chunk = file.slice((n - 1) * CHUNK, Math.min(n * CHUNK, file.size))
      const { presigned_url } = await pub<{ presigned_url: string }>('POST', `/r/${token}/upload/presign-part`,
        { s3_key: init.s3_key, upload_id: init.upload_id, part_number: n })
      // One retry per part: a dropped part costs 10 MB, not the whole file.
      let put = await fetch(presigned_url, { method: 'PUT', body: chunk }).catch(() => null)
      if (!put || !put.ok) put = await fetch(presigned_url, { method: 'PUT', body: chunk })
      if (!put.ok) throw new Error('The upload stopped. Drop the file again.')
      parts.push({ PartNumber: n, ETag: put.headers.get('ETag') ?? '' })
      onProgress(n / total)
    }
    await pub('POST', `/r/${token}/upload/complete`, { s3_key: init.s3_key, upload_id: init.upload_id, parts })
  } catch (e) {
    await pub('POST', `/r/${token}/upload/abort`, { s3_key: init.s3_key, upload_id: init.upload_id, part_number: 1 }).catch(() => {})
    throw e
  }
  return { asset_id: init.asset_id, version_number: init.version_number }
}
