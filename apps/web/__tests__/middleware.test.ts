import { NextRequest } from 'next/server'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const ORIGIN = 'https://feedback.aditor.ai'

function makeRequest(path: string, cookies: Record<string, string> = {}, headers: Record<string, string> = {}) {
  const cookieHeader = Object.entries(cookies).map(([k, v]) => `${k}=${v}`).join('; ')
  const h = new Headers(headers)
  if (cookieHeader) h.set('cookie', cookieHeader)
  return new NextRequest(new URL(path, ORIGIN), { headers: h })
}

async function loadMiddleware(oidcEnabled: boolean) {
  vi.resetModules()
  process.env.NEXT_PUBLIC_OIDC_ENABLED = oidcEnabled ? 'true' : 'false'
  const mod = await import('../middleware')
  return mod.middleware
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ needs_setup: false }) })))
})

afterEach(() => {
  vi.unstubAllGlobals()
  delete process.env.NEXT_PUBLIC_OIDC_ENABLED
})

describe('middleware /login', () => {
  it('307s a cold signed-out hit straight to the gate, with no intermediate render', async () => {
    const middleware = await loadMiddleware(true)
    const req = makeRequest('/login')
    const res = await middleware(req)
    expect(res.status).toBe(307)
    const location = new URL(res.headers.get('location')!)
    expect(location.pathname).toBe('/auth/oidc/login')
    expect(location.searchParams.get('from')).toBe('/home')
  })

  it('carries a sanitized from= through to the gate redirect', async () => {
    const middleware = await loadMiddleware(true)
    const req = makeRequest('/login?from=%2Fhandin', { ff_setup_done: '1' })
    const res = await middleware(req)
    const location = new URL(res.headers.get('location')!)
    expect(location.searchParams.get('from')).toBe('/handin')
  })

  it('refuses to forward an unsafe from= to the gate', async () => {
    const middleware = await loadMiddleware(true)
    const req = makeRequest('/login?from=%2F%2Fevil.com', { ff_setup_done: '1' })
    const res = await middleware(req)
    const location = new URL(res.headers.get('location')!)
    expect(location.searchParams.get('from')).toBe('/home')
  })

  it('307s a hit that already carries a session straight to its destination, never rendering /login', async () => {
    const middleware = await loadMiddleware(true)
    const req = makeRequest('/login?from=%2Fhome', { ff_access_token: 'a-token' })
    const res = await middleware(req)
    expect(res.status).toBe(307)
    expect(new URL(res.headers.get('location')!).pathname).toBe('/home')
  })

  it('bounces an authenticated hit to its destination even when the gate is disabled', async () => {
    const middleware = await loadMiddleware(false)
    const req = makeRequest('/login', { ff_access_token: 'a-token' })
    const res = await middleware(req)
    expect(res.status).toBe(307)
    expect(new URL(res.headers.get('location')!).pathname).toBe('/home')
  })

  it('renders the form for ?error=, even with a stale session cookie, and never loops back to the gate', async () => {
    const middleware = await loadMiddleware(true)
    const req = makeRequest('/login?error=gate_sign_in_failed', { ff_access_token: 'stale' })
    const res = await middleware(req)
    expect(res.headers.get('location')).toBeNull()
  })

  it('renders the form when the gate is not configured on this instance', async () => {
    const middleware = await loadMiddleware(false)
    const req = makeRequest('/login', { ff_setup_done: '1' })
    const res = await middleware(req)
    expect(res.headers.get('location')).toBeNull()
  })

  it('does not bounce the whop lane to the gate', async () => {
    const middleware = await loadMiddleware(true)
    const req = makeRequest('/login', { ff_auth_provider: 'whop', ff_setup_done: '1' })
    const res = await middleware(req)
    expect(res.headers.get('location')).toBeNull()
  })

  it('lets the client resolve a refresh-token-only session instead of forcing a fresh gate sign-in', async () => {
    const middleware = await loadMiddleware(true)
    const req = makeRequest('/login', { ff_refresh_token: 'r-token', ff_setup_done: '1' })
    const res = await middleware(req)
    expect(res.headers.get('location')).toBeNull()
  })

  it('bounces a cold hit to the gate without any server-side call (no setup-check dependency)', async () => {
    // Regression guard: the gate bounce must never depend on a server-side fetch.
    // Middleware runs inside the web container where the browser's relative
    // NEXT_PUBLIC_API_URL ("/api") is not a resolvable base, so a fetch here throws
    // and used to silently suppress the bounce - leaving the Autoreview shell to flash.
    const middleware = await loadMiddleware(true)
    const fetchSpy = vi.fn(() => Promise.reject(new Error('network down')))
    vi.stubGlobal('fetch', fetchSpy)
    const req = makeRequest('/login')
    const res = await middleware(req)
    expect(res.status).toBe(307)
    expect(new URL(res.headers.get('location')!).pathname).toBe('/auth/oidc/login')
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('leaves protected routes unaffected: still redirects to /login when signed out', async () => {
    const middleware = await loadMiddleware(true)
    const req = makeRequest('/home', { ff_setup_done: '1' })
    const res = await middleware(req)
    expect(res.status).toBe(307)
    expect(new URL(res.headers.get('location')!).pathname).toBe('/login')
  })
})
