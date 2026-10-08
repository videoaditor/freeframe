import { afterEach, expect, it, vi } from 'vitest'
import { POST } from '../route'
function request(url: string, token = 'session') { return new Request('https://app.test/brief-title', { method: 'POST', headers: token ? { 'X-FreeFrame-Token': token } : {}, body: JSON.stringify({ url }) }) }
afterEach(() => vi.unstubAllGlobals())
it('never fetches arbitrary hosts, embedded credentials or redirects', async () => {
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher)
  for (const url of ['http://127.0.0.1/private', 'https://docs.google.com.evil.test/document/d/1234567890', 'https://user@docs.google.com/document/d/1234567890', 'https://docs.google.com:444/document/d/1234567890']) expect(await (await POST(request(url))).json()).toEqual({ title: null })
  expect(fetcher).not.toHaveBeenCalled()
  expect((await POST(request('https://docs.google.com/document/d/1234567890', ''))).status).toBe(401)
})
it('verifies identity then reads only a canonical public document without forwarding credentials', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(new Response('{}')).mockResolvedValueOnce(new Response('<title>Summer &amp; Fall - Google Docs</title>', { headers: { 'Content-Type': 'text/html' } }))
  vi.stubGlobal('fetch', fetcher)
  expect(await (await POST(request('https://docs.google.com/document/d/1234567890/edit?tracking=private'))).json()).toEqual({ title: 'Summer & Fall' })
  expect(fetcher.mock.calls[1][0]).toBe('https://docs.google.com/document/d/1234567890/edit')
  expect(fetcher.mock.calls[1][1]).toMatchObject({ redirect: 'error', cache: 'no-store' })
  expect(fetcher.mock.calls[1][1].headers).toBeUndefined()
})
it('does not fetch documents for expired identities or invent titles for private documents', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(new Response('{}', { status: 401 })); vi.stubGlobal('fetch', fetcher)
  expect((await POST(request('https://docs.google.com/document/d/1234567890'))).status).toBe(401)
  expect(fetcher).toHaveBeenCalledTimes(1)
  fetcher.mockResolvedValueOnce(new Response('{}')).mockResolvedValueOnce(new Response('<title>Sign in - Google Accounts</title>', { headers: { 'Content-Type': 'text/html' } }))
  expect(await (await POST(request('https://docs.google.com/document/d/1234567890'))).json()).toEqual({ title: null })
})
