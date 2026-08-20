import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  setTokens,
  getAccessToken,
  getRefreshToken,
  clearTokens,
  getLiveAccessToken,
  getUsableAccessToken,
  refreshAccessToken,
  refreshAccessTokenQuietly,
} from '../auth'

describe('Token management', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('setTokens stores access and refresh tokens in localStorage', () => {
    setTokens('access-123', 'refresh-456')
    expect(localStorage.getItem('ff_access_token')).toBe('access-123')
    expect(localStorage.getItem('ff_refresh_token')).toBe('refresh-456')
  })

  it('getAccessToken retrieves access token from localStorage', () => {
    localStorage.setItem('ff_access_token', 'my-access-token')
    expect(getAccessToken()).toBe('my-access-token')
  })

  it('getAccessToken returns null when no token stored', () => {
    expect(getAccessToken()).toBeNull()
  })

  it('getRefreshToken retrieves refresh token from localStorage', () => {
    localStorage.setItem('ff_refresh_token', 'my-refresh-token')
    expect(getRefreshToken()).toBe('my-refresh-token')
  })

  it('getRefreshToken returns null when no token stored', () => {
    expect(getRefreshToken()).toBeNull()
  })

  it('clearTokens removes both tokens from localStorage', () => {
    localStorage.setItem('ff_access_token', 'access-123')
    localStorage.setItem('ff_refresh_token', 'refresh-456')

    // Mock window.location.href setter to avoid navigation errors
    const locationMock = { href: '' }
    Object.defineProperty(window, 'location', {
      value: locationMock,
      writable: true,
    })

    clearTokens()

    expect(localStorage.getItem('ff_access_token')).toBeNull()
    expect(localStorage.getItem('ff_refresh_token')).toBeNull()
  })

  it('clearTokens redirects to /login', () => {
    const locationMock = { href: '' }
    Object.defineProperty(window, 'location', {
      value: locationMock,
      writable: true,
    })

    clearTokens()

    expect(window.location.href).toBe('/login')
  })
})

// `exp` is seconds since the epoch, and JWT encodes the payload as base64url.
function tokenExpiringIn(seconds: number): string {
  const payload = JSON.stringify({ sub: 'u1', type: 'access', exp: Math.floor(Date.now() / 1000) + seconds })
  const b64url = btoa(payload).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return `header.${b64url}.signature`
}

describe('getLiveAccessToken', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns the token while it is still valid', () => {
    const token = tokenExpiringIn(600)
    localStorage.setItem('ff_access_token', token)
    expect(getLiveAccessToken()).toBe(token)
  })

  it('returns null for an expired token rather than the token', () => {
    // The bug this guards: an expired token is still *present*, and the public
    // share endpoints answer a dead bearer as "anonymous" instead of 401. A
    // caller that trusts presence then sends neither a session nor a guest
    // identity, and the comment is rejected with no way to tell why.
    localStorage.setItem('ff_access_token', tokenExpiringIn(-1))
    expect(getLiveAccessToken()).toBeNull()
  })

  it('treats a token expiring within the leeway as already dead', () => {
    localStorage.setItem('ff_access_token', tokenExpiringIn(5))
    expect(getLiveAccessToken()).toBeNull()
  })

  it('returns null when nothing is stored', () => {
    expect(getLiveAccessToken()).toBeNull()
  })

  it('returns null for a token that is not a JWT', () => {
    localStorage.setItem('ff_access_token', 'not-a-jwt')
    expect(getLiveAccessToken()).toBeNull()
  })

  it('returns null for a JWT carrying no exp claim', () => {
    const b64url = btoa(JSON.stringify({ sub: 'u1' })).replace(/=+$/, '')
    localStorage.setItem('ff_access_token', `header.${b64url}.signature`)
    expect(getLiveAccessToken()).toBeNull()
  })

  it('decodes base64url payloads that use - and _', () => {
    // A padding-free payload containing bytes that differ between base64 and
    // base64url; plain atob would throw on these.
    const payload = JSON.stringify({ sub: '??>>???', exp: Math.floor(Date.now() / 1000) + 600 })
    const b64url = btoa(payload).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
    expect(b64url).toMatch(/[-_]/)
    localStorage.setItem('ff_access_token', `header.${b64url}.signature`)
    expect(getLiveAccessToken()).not.toBeNull()
  })
})

describe('renewing a lapsed session', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
    // Navigation is how the loud path reports failure, so every test here has
    // to be able to see whether it happened.
    Object.defineProperty(window, 'location', { value: { href: '' }, writable: true })
  })

  function stubRefreshEndpoint(response: { ok: boolean; body?: unknown }) {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: response.ok,
      json: async () => response.body ?? {},
    })
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  it('returns a live token without going to the network', async () => {
    const token = tokenExpiringIn(600)
    localStorage.setItem('ff_access_token', token)
    localStorage.setItem('ff_refresh_token', 'refresh-1')
    const fetchMock = stubRefreshEndpoint({ ok: true })

    expect(await getUsableAccessToken()).toBe(token)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('renews a lapsed token and returns the new one', async () => {
    const renewed = tokenExpiringIn(3600)
    localStorage.setItem('ff_access_token', tokenExpiringIn(-1))
    localStorage.setItem('ff_refresh_token', 'refresh-1')
    stubRefreshEndpoint({ ok: true, body: { access_token: renewed, refresh_token: 'refresh-2' } })

    expect(await getUsableAccessToken()).toBe(renewed)
    expect(localStorage.getItem('ff_access_token')).toBe(renewed)
    expect(localStorage.getItem('ff_refresh_token')).toBe('refresh-2')
  })

  it('gives up silently when there is nothing to renew', async () => {
    localStorage.setItem('ff_access_token', tokenExpiringIn(-1))
    const fetchMock = stubRefreshEndpoint({ ok: true })

    expect(await getUsableAccessToken()).toBeNull()
    expect(fetchMock).not.toHaveBeenCalled()
    // The caller is a public share link. Somebody with no account is an
    // ordinary visitor there, not an error to redirect away.
    expect(window.location.href).toBe('')
  })

  it('leaves a viewer on the page when the refresh itself is refused', async () => {
    localStorage.setItem('ff_access_token', tokenExpiringIn(-1))
    localStorage.setItem('ff_refresh_token', 'expired-refresh')
    stubRefreshEndpoint({ ok: false })

    expect(await refreshAccessTokenQuietly()).toBeNull()
    expect(window.location.href).toBe('')
  })

  it('still sends the dashboard to /login when its refresh is refused', async () => {
    localStorage.setItem('ff_access_token', tokenExpiringIn(-1))
    localStorage.setItem('ff_refresh_token', 'expired-refresh')
    stubRefreshEndpoint({ ok: false })

    expect(await refreshAccessToken()).toBeNull()
    expect(localStorage.getItem('ff_refresh_token')).toBeNull()
    expect(window.location.href).toBe('/login')
  })

  it('runs one refresh for concurrent callers', async () => {
    const renewed = tokenExpiringIn(3600)
    localStorage.setItem('ff_access_token', tokenExpiringIn(-1))
    localStorage.setItem('ff_refresh_token', 'refresh-1')
    const fetchMock = stubRefreshEndpoint({ ok: true, body: { access_token: renewed } })

    const results = await Promise.all([getUsableAccessToken(), getUsableAccessToken()])

    expect(results).toEqual([renewed, renewed])
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
