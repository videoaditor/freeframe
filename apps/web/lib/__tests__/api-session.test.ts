import { afterEach, expect, it, vi } from 'vitest'
import { api } from '../api'
import { setTokens } from '../auth'

const token = (sub: string, revision = 0) => `header.${btoa(JSON.stringify({ sub, revision }))}.signature`
afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })

it.each(['patch', 'upload'] as const)('does not replay %s under a replacement owner after a delayed 401', async method => {
  setTokens(token('owner-a'), 'refresh-a', 'whop')
  let finish!: (response: Response) => void
  const first = new Promise<Response>(resolve => { finish = resolve })
  const fetcher = vi.fn().mockReturnValueOnce(first).mockResolvedValue(new Response(JSON.stringify({
    access_token: token('owner-b'), refresh_token: 'refresh-b-next',
  }), { headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetcher)
  const request = method === 'patch'
    ? api.patch('/auth/me/preferences', { theme: 'dark' })
    : api.upload('/auth/me/avatar', new FormData())
  setTokens(token('owner-b'), 'refresh-b', 'whop')
  finish(new Response(JSON.stringify({ detail: 'Token expired' }), { status: 401 }))
  await expect(request).rejects.toMatchObject({ status: 401 })
  expect(fetcher).toHaveBeenCalledTimes(1)
  expect(localStorage.getItem('ff_refresh_token')).toBe('refresh-b')
})

it('still renews a late request after a concurrent token rotation for the same staff account', async () => {
  setTokens(token('staff'), 'refresh-staff')
  let finish!: (response: Response) => void
  const first = new Promise<Response>(resolve => { finish = resolve })
  const fetcher = vi.fn()
    .mockReturnValueOnce(first)
    .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: token('staff', 2), refresh_token: 'rotated' })))
    .mockResolvedValueOnce(new Response(JSON.stringify({ saved: true }), { headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetcher)
  const request = api.patch('/auth/me/preferences', { theme: 'dark' })
  setTokens(token('staff', 1), 'already-rotated')
  finish(new Response('{}', { status: 401 }))
  expect(await request).toEqual({ saved: true })
  expect(localStorage.getItem('ff_refresh_token')).toBe('rotated')
})
