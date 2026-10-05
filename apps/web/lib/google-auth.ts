// "Continue with Google": the browser goes to Google and comes back to /login/google with a code.
// The API trades the code for a verified email (apps/api/services/google_auth.py). The state
// lives in sessionStorage for this one round trip and is the CSRF check.
export const GOOGLE_STATE_KEY = 'ff_google_state'
export const GOOGLE_FROM_KEY = 'ff_google_from'

export function googleRedirectUri(origin: string): string {
  return `${origin}/login/google`
}

export function googleAuthorizeUrl(clientId: string, origin: string, state: string): string {
  const q = new URLSearchParams({
    client_id: clientId,
    redirect_uri: googleRedirectUri(origin),
    response_type: 'code',
    scope: 'openid email',
    prompt: 'select_account',
    state,
  })
  return `https://accounts.google.com/o/oauth2/v2/auth?${q}`
}
