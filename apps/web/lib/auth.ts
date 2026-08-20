const ACCESS_TOKEN_KEY = 'ff_access_token'
const REFRESH_TOKEN_KEY = 'ff_refresh_token'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null
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
 * Read the `exp` claim without verifying the signature - verification is the
 * server's job; the client only needs to know whether sending this is futile.
 * Returns null for anything unparseable, which callers treat as expired.
 */
function readExpiry(token: string): number | null {
  const payload = token.split('.')[1]
  if (!payload) return null
  try {
    // JWT uses base64url; atob wants base64.
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    const exp = (JSON.parse(json) as { exp?: unknown }).exp
    return typeof exp === 'number' ? exp : null
  } catch {
    return null
  }
}

/** True while the stored access token is present and not past its `exp`. */
export function hasLiveSession(): boolean {
  return getLiveAccessToken() !== null
}

/**
 * The access token, but only while it is still usable. Prefer this over
 * `getAccessToken` on any request that cannot refresh - a share link, an
 * EventSource URL - where sending a dead token is worse than sending none.
 */
export function getLiveAccessToken(): string | null {
  const token = getAccessToken()
  if (!token) return null
  const exp = readExpiry(token)
  if (exp === null) return null
  return exp - EXPIRY_LEEWAY_SECONDS > Date.now() / 1000 ? token : null
}

export function setTokens(access: string, refresh: string): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(ACCESS_TOKEN_KEY, access)
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh)
  // Set cookies so middleware can check auth on server side
  document.cookie = `${ACCESS_TOKEN_KEY}=${access}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`
  document.cookie = `${REFRESH_TOKEN_KEY}=${refresh}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`
}

export function clearTokens(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  // Clear auth cookies
  document.cookie = `${ACCESS_TOKEN_KEY}=; path=/; max-age=0`
  document.cookie = `${REFRESH_TOKEN_KEY}=; path=/; max-age=0`
  window.location.href = '/login'
}

// Deduplicate concurrent refresh calls — when access token expires, multiple
// API calls may simultaneously get 401 and try to refresh. Only one should run.
let _refreshPromise: Promise<string | null> | null = null

export async function refreshAccessToken(): Promise<string | null> {
  if (_refreshPromise) return _refreshPromise

  _refreshPromise = _doRefresh()
  try {
    return await _refreshPromise
  } finally {
    _refreshPromise = null
  }
}

async function _doRefresh(): Promise<string | null> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) {
    clearTokens()
    return null
  }

  try {
    const response = await fetch(`${API_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })

    if (!response.ok) {
      clearTokens()
      return null
    }

    const data = await response.json()
    const newAccessToken: string = data.access_token
    const newRefreshToken: string = data.refresh_token ?? refreshToken

    setTokens(newAccessToken, newRefreshToken)
    return newAccessToken
  } catch {
    clearTokens()
    return null
  }
}
