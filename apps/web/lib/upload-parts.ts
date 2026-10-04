import { ApiError } from './api'

export const CHUNK_SIZE = 10 * 1024 * 1024 // 10 MB
export const PARTS_IN_FLIGHT = 3           // hides per-part latency without flooding an editor's uplink
export const FILES_IN_FLIGHT = 2           // more at once just shares one uplink, and one hiccup then fails them all
export const PART_ATTEMPTS = 5

const isAbort = (e: unknown) => e instanceof DOMException && e.name === 'AbortError'

/** A dropped connection ("Failed to fetch") or a server that blinked is worth another try; a refusal is not. */
export function isRetryable(e: unknown): boolean {
  if (isAbort(e)) return false
  if (e instanceof ApiError) return e.status === 408 || e.status === 429 || e.status >= 500
  if (e instanceof PartHttpError) return e.status === 403 || e.status === 408 || e.status === 429 || e.status >= 500
  return e instanceof TypeError
}

export class PartHttpError extends Error {
  status: number
  constructor(status: number, statusText: string, part: number) {
    super(`Part ${part} failed: ${statusText || status}`)
    this.name = 'PartHttpError'
    this.status = status
  }
}

const wait = (ms: number, signal?: AbortSignal) => new Promise<void>((resolve, reject) => {
  if (signal?.aborted) return reject(new DOMException('Upload cancelled', 'AbortError'))
  const t = setTimeout(resolve, ms)
  signal?.addEventListener('abort', () => { clearTimeout(t); reject(new DOMException('Upload cancelled', 'AbortError')) }, { once: true })
})

/** Run `fn` up to `attempts` times, backing off between tries. Re-running re-signs the part, so an expired URL heals too. */
export async function withRetry<T>(fn: () => Promise<T>, signal?: AbortSignal, attempts = PART_ATTEMPTS, baseMs = 1000): Promise<T> {
  for (let attempt = 1; ; attempt++) {
    try {
      return await fn()
    } catch (e) {
      if (attempt >= attempts || !isRetryable(e)) throw e
      await wait(baseMs * 2 ** (attempt - 1), signal)
    }
  }
}

export interface UploadedPart { PartNumber: number; ETag: string }

/**
 * Upload every part of `file`, three at a time, each part retried on its own. Progress is bytes sent.
 * Parts are independent, so retrying one never restarts the file.
 */
export async function uploadParts(opts: {
  file: Blob
  presign: (partNumber: number) => Promise<string>
  signal?: AbortSignal
  onProgress?: (fraction: number) => void
  putPart?: (url: string, body: Blob, signal?: AbortSignal) => Promise<Response>
  baseMs?: number
}): Promise<UploadedPart[]> {
  const { file, presign, signal, onProgress, baseMs } = opts
  const put = opts.putPart ?? ((url, body, sig) => fetch(url, { method: 'PUT', body, signal: sig }))
  const total = Math.max(1, Math.ceil(file.size / CHUNK_SIZE))
  const parts: UploadedPart[] = []
  let next = 1, sent = 0, failed = false
  const worker = async () => {
    while (next <= total && !failed) {
      const n = next++
      try {
        if (signal?.aborted) throw new DOMException('Upload cancelled', 'AbortError')
        const chunk = file.slice((n - 1) * CHUNK_SIZE, Math.min(n * CHUNK_SIZE, file.size))
        const etag = await withRetry(async () => {
          const url = await presign(n)
          const res = await put(url, chunk, signal)
          if (!res.ok) throw new PartHttpError(res.status, res.statusText, n)
          return res.headers.get('ETag') ?? ''
        }, signal, PART_ATTEMPTS, baseMs)
        parts.push({ PartNumber: n, ETag: etag })
        sent += chunk.size
        onProgress?.(file.size ? sent / file.size : 1)
      } catch (e) { failed = true; throw e }
    }
  }
  // Wait for every worker before reporting: no part may still be writing after the caller cleans up.
  const results = await Promise.allSettled(Array.from({ length: Math.min(PARTS_IN_FLIGHT, total) }, worker))
  const failure = results.find((r): r is PromiseRejectedResult => r.status === 'rejected')
  if (failure) throw failure.reason
  return parts.sort((a, b) => a.PartNumber - b.PartNumber)
}

// Files wait their turn instead of all starting at once. Module-level on purpose: one editor, one uplink.
let active = 0
const waiting: (() => void)[] = []
export async function acquireUploadSlot(signal?: AbortSignal, limit = FILES_IN_FLIGHT): Promise<() => void> {
  if (active >= limit) {
    await new Promise<void>((resolve, reject) => {
      const go = () => { signal?.removeEventListener('abort', onAbort); resolve() }
      const onAbort = () => { const i = waiting.indexOf(go); if (i >= 0) waiting.splice(i, 1); reject(new DOMException('Upload cancelled', 'AbortError')) }
      waiting.push(go)
      signal?.addEventListener('abort', onAbort, { once: true })
    })
  }
  active++
  let released = false
  return () => { if (released) return; released = true; active--; waiting.shift()?.() }
}
