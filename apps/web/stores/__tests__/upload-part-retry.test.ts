import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/lib/api', () => ({ api: { post: vi.fn(), get: vi.fn() } }))

import { api } from '@/lib/api'
import { uploadPart, uploadAllParts } from '../upload-store'

const ok = () => new Response(null, { status: 200, headers: { ETag: '"abc"' } })

describe('uploadPart', () => {
  beforeEach(() => {
    vi.mocked(api.post).mockResolvedValue({ presigned_url: 'https://s3/part' })
  })

  it('survives dropped connections and a 5xx, re-presigning each try', async () => {
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(ok())
    vi.stubGlobal('fetch', fetchMock)
    const etag = await uploadPart(new Blob(['x']), 'k', 'u', 1, new AbortController().signal, [0, 0, 0])
    expect(etag).toBe('"abc"')
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(api.post).toHaveBeenCalledTimes(3)
  })

  it('gives up with a readable message after the last retry', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(uploadPart(new Blob(['x']), 'k', 'u', 1, new AbortController().signal, [0, 0]))
      .rejects.toThrow('Connection dropped during upload')
  })

  it('does not retry a 403', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 403 }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(uploadPart(new Blob(['x']), 'k', 'u', 1, new AbortController().signal, [0, 0]))
      .rejects.toThrow('403')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('stops immediately when cancelled', async () => {
    const c = new AbortController()
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => { c.abort(); return Promise.reject(new DOMException('x', 'AbortError')) }))
    await expect(uploadPart(new Blob(['x']), 'k', 'u', 1, c.signal, [0])).rejects.toMatchObject({ name: 'AbortError' })
  })
})

describe('uploadAllParts', () => {
  it('runs at most 4 parts at once across files and returns parts in order', async () => {
    vi.mocked(api.post).mockImplementation(async (_url, body) => ({ presigned_url: `https://s3/${(body as { part_number: number }).part_number}` }))
    let active = 0
    let peak = 0
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async (url: string) => {
      active++
      peak = Math.max(peak, active)
      await new Promise((r) => setTimeout(r, 5))
      active--
      return new Response(null, { status: 200, headers: { ETag: `"${url.split('/').pop()}"` } })
    }))
    const big = new Blob([new Uint8Array(10 * 1024 * 1024 * 5 + 1)]) // 6 parts
    const signal = new AbortController().signal
    const [a, b] = await Promise.all([
      uploadAllParts(big, 'k1', 'u1', signal, () => {}),
      uploadAllParts(big, 'k2', 'u2', signal, () => {}),
    ])
    expect(peak).toBe(4)
    expect(a.map((p) => p.PartNumber)).toEqual([1, 2, 3, 4, 5, 6])
    expect(b.map((p) => p.ETag)).toEqual(['"1"', '"2"', '"3"', '"4"', '"5"', '"6"'])
  })
})
