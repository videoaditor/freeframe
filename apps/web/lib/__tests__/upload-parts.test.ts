import { afterEach, describe, expect, it, vi } from 'vitest'
import { acquireUploadSlot, CHUNK_SIZE, uploadParts } from '../upload-parts'

const file = (parts: number) => new Blob([new Uint8Array(parts * CHUNK_SIZE - 5)])
const ok = () => new Response('', { headers: { ETag: 'e' } })

describe('uploadParts', () => {
  it('retries a part that fails with a dropped connection, without restarting the file', async () => {
    const calls: Record<string, number> = {}
    const parts = await uploadParts({
      file: file(3), baseMs: 1,
      presign: async (n) => `u${n}`,
      putPart: async (url) => { calls[url] = (calls[url] || 0) + 1; if (url === 'u2' && calls[url] < 3) throw new TypeError('Failed to fetch'); return ok() },
    })
    expect(parts.map(p => p.PartNumber)).toEqual([1, 2, 3])
    expect(calls).toEqual({ u1: 1, u2: 3, u3: 1 })
  })
  it('re-signs the part on every try, so an expired URL heals', async () => {
    let signs = 0
    await uploadParts({ file: file(1), baseMs: 1, presign: async () => `u${++signs}`,
      putPart: async (url) => url === 'u1' ? new Response('', { status: 403 }) : ok() })
    expect(signs).toBe(2)
  })
  it('gives up after twelve tries and reports the real error', async () => {
    const put = vi.fn(async () => { throw new TypeError('Failed to fetch') })
    await expect(uploadParts({ file: file(1), baseMs: 1, presign: async () => 'u', putPart: put })).rejects.toThrow(/Failed to fetch \(stopped at 0 of 10 MB after \d+s, [\d.]+ Mbit\/s average\)/)
    expect(put).toHaveBeenCalledTimes(12)
  })
  it('does not retry a refusal', async () => {
    const put = vi.fn(async () => new Response('', { status: 400, statusText: 'Bad Request' }))
    await expect(uploadParts({ file: file(1), baseMs: 1, presign: async () => 'u', putPart: put })).rejects.toThrow('Part 1 failed')
    expect(put).toHaveBeenCalledTimes(1)
  })
  it('uploads at most three parts together and reports byte progress', async () => {
    let active = 0, peak = 0
    const progress: number[] = []
    await uploadParts({ file: file(6), presign: async (n) => `u${n}`, onProgress: f => progress.push(f),
      putPart: async () => { active++; peak = Math.max(peak, active); await new Promise(r => setTimeout(r, 5)); active--; return ok() } })
    expect(peak).toBe(3)
    expect(progress[progress.length - 1]).toBe(1)
  })
  it('stops when cancelled', async () => {
    const c = new AbortController(); c.abort()
    await expect(uploadParts({ file: file(2), presign: async () => 'u', signal: c.signal, putPart: async () => ok() })).rejects.toThrow('cancelled')
  })
})

describe('acquireUploadSlot', () => {
  it('lets two files go and holds the third until one finishes', async () => {
    const a = await acquireUploadSlot(), b = await acquireUploadSlot()
    let thirdStarted = false
    const third = acquireUploadSlot().then(r => { thirdStarted = true; return r })
    await new Promise(r => setTimeout(r, 10))
    expect(thirdStarted).toBe(false)
    a()
    const release3 = await third
    expect(thirdStarted).toBe(true)
    b(); release3()
  })
  it('a queued file that is cancelled leaves the line', async () => {
    const a = await acquireUploadSlot(), b = await acquireUploadSlot()
    const c = new AbortController()
    const q = acquireUploadSlot(c.signal)
    c.abort()
    await expect(q).rejects.toThrow('cancelled')
    a()
    const next = await acquireUploadSlot()       // not blocked by the cancelled one
    b(); next()
  })
})

describe('a lost connection', () => {
  afterEach(() => vi.unstubAllGlobals())
  it('waits for the browser to come back online without burning tries, then finishes', async () => {
    const listeners: Record<string, () => void> = {}
    vi.stubGlobal('navigator', { onLine: false })
    vi.stubGlobal('window', { addEventListener: (n: string, f: () => void) => { listeners[n] = f }, removeEventListener: () => {} })
    let calls = 0
    const job = uploadParts({ file: file(1), baseMs: 1, presign: async () => 'u',
      putPart: async () => { calls++; if (calls === 1) throw new TypeError('Failed to fetch'); return ok() } })
    await new Promise(r => setTimeout(r, 20))
    expect(calls).toBe(1)                                  // still offline: not retrying, not failed
    vi.stubGlobal('navigator', { onLine: true }); listeners.online()
    expect((await job).map(p => p.PartNumber)).toEqual([1])
    expect(calls).toBe(2)
  })
  it('survives more failures than the old five-try limit', async () => {
    let calls = 0
    const parts = await uploadParts({ file: file(1), baseMs: 1, presign: async () => 'u',
      putPart: async () => { if (++calls < 9) throw new TypeError('Failed to fetch'); return ok() } })
    expect(parts).toHaveLength(1)
    expect(calls).toBe(9)
  })
})
