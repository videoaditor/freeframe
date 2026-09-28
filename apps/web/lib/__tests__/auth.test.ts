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

it('Whop entry clears tokens and customer-specific persisted data before exchanging identity', async () => {
  const { resetWhopEntry } = await import('../auth')
  localStorage.setItem('ff_access_token', 'old-owner')
  localStorage.setItem('ff_refresh_token', 'old-refresh')
  localStorage.setItem('ff-uploads', 'old-private-files')
  localStorage.setItem('ff-branding', 'old-brand')
  resetWhopEntry()
  expect(getAccessToken()).toBeNull()
  expect(getRefreshToken()).toBeNull()
  expect(localStorage.getItem('ff-uploads')).toBeNull()
  expect(localStorage.getItem('ff-branding')).toBeNull()
  expect(localStorage.getItem('ff_auth_provider')).toBe('whop')
})

it('a successful ordinary login replaces a previous Whop sign-in method', () => {
  localStorage.setItem('ff_auth_provider', 'whop')
  document.cookie = 'ff_auth_provider=whop; path=/'
  setTokens('staff-access', 'staff-refresh')
  expect(localStorage.getItem('ff_auth_provider')).toBeNull()
  expect(document.cookie).not.toContain('ff_auth_provider=whop')
})

it('refresh keeps a successful Whop session in the Whop sign-in lane', async () => {
  localStorage.setItem('ff_auth_provider', 'whop')
  localStorage.setItem('ff_refresh_token', 'whop-refresh')
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
    ok: true, json: async () => ({ access_token: 'renewed', refresh_token: 'renewed-refresh' }),
  } as Response)
  expect(await refreshAccessTokenQuietly()).toBe('renewed')
  expect(localStorage.getItem('ff_auth_provider')).toBe('whop')
  fetchMock.mockRestore()
})

it('a pending refresh cannot restore the previous owner after Whop entry clears it', async () => {
  const { resetWhopEntry } = await import('../auth')
  setTokens('old-access', 'old-refresh')
  let complete!: (value: Response) => void
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => new Promise(resolve => { complete = resolve }))
  const refreshing = refreshAccessTokenQuietly()
  resetWhopEntry()
  complete({ ok: true, json: async () => ({ access_token: 'stale-access', refresh_token: 'stale-refresh' }) } as Response)
  await refreshing
  expect(getAccessToken()).toBeNull()
  expect(getRefreshToken()).toBeNull()
  fetchMock.mockRestore()
})

it('a stale refresh never supplies the new owner token for retrying an old mutation', async () => {
  setTokens('old-access', 'old-refresh')
  let complete!: (value: Response) => void
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => new Promise(resolve => { complete = resolve }))
  const refreshing = refreshAccessToken()
  const newAccess = `header.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.signature`
  setTokens(newAccess, 'new-owner-refresh', 'whop')
  complete({ ok: true, json: async () => ({ access_token: 'stale-access', refresh_token: 'stale-refresh' }) } as Response)
  expect(await refreshing).toBeNull()
  expect(getAccessToken()).toBe(newAccess)
  expect(getRefreshToken()).toBe('new-owner-refresh')
  fetchMock.mockRestore()
})
