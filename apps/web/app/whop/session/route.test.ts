import { afterEach, expect, it, vi } from 'vitest'
import { POST } from './route'

afterEach(() => vi.unstubAllGlobals())
it('requires the injected header, never an email or token in the body', async () => {
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher)
  const result = await POST(new Request('https://app.example/whop/session', { method: 'POST', body: '{"email":"owner@example.com"}' }))
  expect(result.status).toBe(401)
  expect(fetcher).not.toHaveBeenCalled()
})
it('forwards only the Whop token and returns only FreeFrame credentials', async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json({ access_token: 'access', refresh_token: 'refresh', private: 'secret' }))
  vi.stubGlobal('fetch', fetcher)
  const result = await POST(new Request('https://app.example/whop/session', { method: 'POST', headers: { 'x-whop-user-token': 'injected', authorization: 'untrusted' } }))
  expect(fetcher.mock.calls[0][1].headers).toEqual({ 'x-whop-user-token': 'injected' })
  expect(await result.json()).toEqual({ access_token: 'access', refresh_token: 'refresh' })
  expect(result.headers.get('cache-control')).toBe('no-store')
})
it('does not leak upstream error bodies', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ detail: 'sensitive internal details' }, { status: 500 })))
  const result = await POST(new Request('https://app.example/whop/session', { method: 'POST', headers: { 'x-whop-user-token': 'injected' } }))
  expect(result.status).toBe(503)
  expect(JSON.stringify(await result.json())).not.toContain('sensitive')
})
