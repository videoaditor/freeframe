const ACCESS_TOKEN_KEY = 'ff_access_token'
const REFRESH_TOKEN_KEY = 'ff_refresh_token'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

// A gate (OIDC) sign-in reaches the browser only as a server redirect that set
// `ff_access_token`/`ff_refresh_token` cookies (apps/api/routers/auth.py's
// /auth/oidc/callback) - there is no page JS in that flow to call setTokens().
// Adopt them into localStorage once, on first read, so every call site below
// can keep treating localStorage as the one source of truth, exactly as it
// does for a password sign-in.
function adoptCookieSessionIfNeeded(): void {
  if (localStorage.getItem(ACCESS_TOKEN_KEY)) return
  const access = readCookie(ACCESS_TOKEN_KEY)
  const refresh = readCookie(REFRESH_TOKEN_KEY)
  if (access && refresh) {
    localStorage.setItem(ACCESS_TOKEN_KEY, access)
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh)
  }
}

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null
  adoptCookieSessionIfNeeded()
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null
  adoptCookieSessionIfNeeded()
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

// A token that expired an hour ago still looks like a session to
// `localStorage.getItem(...)`. Most of the app gets away with that because the
// authenticated API answers a dead bearer with 401 and `api.ts` refreshes and
// retries. The public share endpoints do not: they treat an unusable bearer as
// "anonymous" and carry on, so a caller that trusts mere presence there sends
// neither a session nor a guest identity and gets rejected. Anything deciding
// "is somebody signed in" must therefore ask whether the token is still live,
// not whether one is stored.

/** Seconds of headroom, so a token that dies mid-flight is treated as dead. */
const EXPIRY_LEEWAY_SECONDS = 30

/**
 * Read a claim without verifying the signature; the server still authenticates
 * the token. The client uses this only to reject expired or cross-account retries.
 */
function readTokenClaim(token: string | null, claim: string): unknown {
  const payload = token?.split('.')[1]
  if (!payload) return null
  try {
    // JWT uses base64url; atob wants base64.
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    return (JSON.parse(json) as Record<string, unknown>)[claim]
  } catch {
    return null
  }
}

/**
 * The access token, but only while it is still usable. Prefer this over
 * `getAccessToken` on any request that cannot refresh - a share link, an
 * EventSource URL - where sending a dead token is worse than sending none.
 */
export function getLiveAccessToken(): string | null {
  const token = getAccessToken()
  if (!token) return null
  const exp = readTokenClaim(token, 'exp')
  if (typeof exp !== 'number') return null
  return exp - EXPIRY_LEEWAY_SECONDS > Date.now() / 1000 ? token : null
}

export function setTokens(access: string, refresh: string, provider: 'email' | 'whop' = 'email'): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(ACCESS_TOKEN_KEY, access)
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh)
  if (provider === 'whop') {
    localStorage.setItem('ff_auth_provider', 'whop')
    document.cookie = 'ff_auth_provider=whop; path=/; max-age=604800; SameSite=Lax'
  } else {
    localStorage.removeItem('ff_auth_provider')
    document.cookie = 'ff_auth_provider=; path=/; max-age=0'
  }
  // Set cookies so middleware can check auth on server side
  document.cookie = `${ACCESS_TOKEN_KEY}=${access}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`
  document.cookie = `${REFRESH_TOKEN_KEY}=${refresh}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`
}

export function clearTokens(): void {
  if (typeof window === 'undefined') return
  const isWhop = localStorage.getItem('ff_auth_provider') === 'whop'
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  // Clear auth cookies
  document.cookie = `${ACCESS_TOKEN_KEY}=; path=/; max-age=0`
  document.cookie = `${REFRESH_TOKEN_KEY}=; path=/; max-age=0`
  const from = window.location.pathname === '/handin' ? window.location.pathname + window.location.search : ''
  if (isWhop) {
    window.location.href = from ? '/whop?from=' + encodeURIComponent(from) : '/whop'
    return
  }
  // Route every non-Whop sign-out through the gate logout endpoint so a gate
  // (OIDC) session's SSO also ends, not just this app's own cookies - it
  // falls back to a plain /login redirect when the gate isn't configured, so
  // this is safe for a password sign-in too.
  const params = from ? `?from=${encodeURIComponent(from)}` : ''
  window.location.href = `${API_URL}/auth/oidc/logout${params}`
}

/** Start a Whop identity exchange without inheriting a previous owner's session. */
export function resetWhopEntry(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  localStorage.removeItem('ff-uploads')
  localStorage.removeItem('ff-branding')
  localStorage.setItem('ff_auth_provider', 'whop')
  document.cookie = `${ACCESS_TOKEN_KEY}=; path=/; max-age=0`
  document.cookie = `${REFRESH_TOKEN_KEY}=; path=/; max-age=0`
  document.cookie = 'ff_auth_provider=whop; path=/; max-age=604800; SameSite=Lax'
}

// Deduplicate concurrent refresh calls — when access token expires, multiple
// API calls may simultaneously get 401 and try to refresh. Only one should run.
let _refreshPromise: Promise<string | null> | null = null

/**
 * Renew the session without touching the page. Returns null when it cannot be
 * renewed, leaving the caller to decide what that means.
 *
 * A share link is reachable without an account, so "your session is gone" is an
 * ordinary state there rather than an error: sending that viewer to /login would
 * throw a client at a sign-in page they have no account for, in the middle of
 * reviewing the video somebody sent them. Anything rendered on a public route
 * must refresh through this, never through `refreshAccessToken`.
 */
export async function refreshAccessTokenQuietly(): Promise<string | null> {
  if (_refreshPromise) return _refreshPromise

  _refreshPromise = _doRefresh()
  try {
    return await _refreshPromise
  } finally {
    _refreshPromise = null
  }
}

/**
 * Renew the session, and treat failure as being logged out: tokens cleared and
 * the browser sent to /login. Correct behind the dashboard, where every route
 * needs an account anyway.
 */
function sameAccount(original: string | null, current: string | null): boolean {
  if (original === current) return true
  const subject = readTokenClaim(original, 'sub')
  return typeof subject === 'string' && !!subject && subject === readTokenClaim(current, 'sub')
}

export async function refreshAccessToken(expectedAccessToken = getAccessToken()): Promise<string | null> {
  // A delayed 401 belongs to its original account, even if another tab has signed in.
  if (!sameAccount(expectedAccessToken, getAccessToken())) return null
  const originalSession = getRefreshToken()
  const token = await refreshAccessTokenQuietly()
  if (!sameAccount(expectedAccessToken, getAccessToken())) return null
  if (!token && getRefreshToken() === originalSession) clearTokens()
  return token
}

/**
 * A usable access token, renewing a lapsed one once if the session allows it.
 * Prefer this wherever a stale token would otherwise be sent or, worse, be
 * mistaken for a live session. Resolves to null when there is nothing to renew,
 * which callers on public routes should read as "ask who this person is".
 */
export async function getUsableAccessToken(): Promise<string | null> {
  const live = getLiveAccessToken()
  if (live) return live
  if (!getRefreshToken()) return null
  return refreshAccessTokenQuietly()
}

async function _doRefresh(): Promise<string | null> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return null

  try {
    const response = await fetch(`${API_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })

    if (getRefreshToken() !== refreshToken) return null
    if (!response.ok) return null

    const data = await response.json()
    // A Whop entry or another login may have replaced this session while we waited.
    if (getRefreshToken() !== refreshToken) return null
    const newAccessToken: string = data.access_token
    const newRefreshToken: string = data.refresh_token ?? refreshToken

    setTokens(newAccessToken, newRefreshToken, localStorage.getItem('ff_auth_provider') === 'whop' ? 'whop' : 'email')
    return newAccessToken
  } catch {
    return null
  }
}
