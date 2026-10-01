import { afterEach, expect, it, vi } from 'vitest'
import { uploadToRequest } from '../platform'

afterEach(() => vi.unstubAllGlobals())

it('uploads at most three parts together and completes in part order with byte progress', async () => {
  const releases: (() => void)[] = []
  let active = 0, peak = 0
  let complete: { parts: { PartNumber: number }[] } | undefined
  vi.stubGlobal('fetch', vi.fn(async (url: string, opts: RequestInit) => {
    if (url.endsWith('/initiate')) return Response.json({ upload_id: 'u', s3_key: 'k', asset_id: 'a', version_number: 1 })
    if (url.endsWith('/presign-part')) return Response.json({ presigned_url: `https://upload.test/${JSON.parse(String(opts.body)).part_number}` })
    if (url.startsWith('https://upload.test/')) {
      active++; peak = Math.max(peak, active)
      await new Promise<void>(resolve => releases.push(resolve))
      active--
      return new Response('', { headers: { ETag: 'etag' } })
    }
    if (url.endsWith('/complete')) complete = JSON.parse(String(opts.body))
    return Response.json({})
  }))
  const progress: number[] = []
  const job = uploadToRequest('t', { name: 'Editor', email: 'e@example.test' }, new File([new Uint8Array(31 * 1024 * 1024)], 'ad.mp4'), p => progress.push(p))
  await vi.waitFor(() => expect(releases.length).toBe(3))
  releases[2](); releases[0](); releases[1]()
  await vi.waitFor(() => expect(releases.length).toBe(4))
  releases[3]()
  await job
  expect(peak).toBe(3)
  expect(complete?.parts.map(p => p.PartNumber)).toEqual([1, 2, 3, 4])
  expect(progress[0]).toBeCloseTo(10 / 31)
  expect(progress.at(-1)).toBe(1)
})

it('settles in-flight parts before aborting and never completes a failed upload', async () => {
  let release: () => void = () => {}
  let aborted = false, completed = false
  vi.stubGlobal('fetch', vi.fn(async (url: string, opts: RequestInit) => {
    if (url.endsWith('/initiate')) return Response.json({ upload_id: 'u', s3_key: 'k', asset_id: 'a' })
    if (url.endsWith('/presign-part')) return Response.json({ presigned_url: `https://upload.test/${JSON.parse(String(opts.body)).part_number}` })
    if (url === 'https://upload.test/1') return new Response('', { status: 500 })
    if (url.startsWith('https://upload.test/')) { await new Promise<void>(r => { release = r }); return new Response('', { headers: { ETag: 'ok' } }) }
    if (url.endsWith('/abort')) aborted = true
    if (url.endsWith('/complete')) completed = true
    return Response.json({})
  }))
  const result = uploadToRequest('t', { name: 'E', email: 'e@test.com' }, new File([new Uint8Array(11 * 1024 * 1024)], 'ad.mp4'), () => {}).catch(e => e)
  await vi.waitFor(() => expect(vi.mocked(fetch).mock.calls.filter(([url]) => url === 'https://upload.test/1')).toHaveLength(2))
  expect(aborted).toBe(false)
  release()
  expect(await result).toBeInstanceOf(Error)
  expect(aborted).toBe(true)
  expect(completed).toBe(false)
})
