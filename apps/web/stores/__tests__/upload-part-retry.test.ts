import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/lib/api', () => ({ api: { post: vi.fn(), get: vi.fn() } }))

import { api } from '@/lib/api'
import { uploadPart } from '../upload-store'

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
