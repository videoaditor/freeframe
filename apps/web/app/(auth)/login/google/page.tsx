'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { api, ApiError } from '@/lib/api'
import { setTokens } from '@/lib/auth'
import { GOOGLE_FROM_KEY, GOOGLE_STATE_KEY, googleRedirectUri } from '@/lib/google-auth'
import type { AuthTokens } from '@/types'

/** Google sends the browser back here with ?code=&state=. Trade the code, then land like a magic code. */
export default function GoogleCallbackPage() {
  const started = useRef(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (started.current) return
    started.current = true
    const q = new URLSearchParams(window.location.search)
    const expected = sessionStorage.getItem(GOOGLE_STATE_KEY)
    const from = sessionStorage.getItem(GOOGLE_FROM_KEY) || ''
    sessionStorage.removeItem(GOOGLE_STATE_KEY)
    sessionStorage.removeItem(GOOGLE_FROM_KEY)
    const code = q.get('code')
    if (!code || !expected || q.get('state') !== expected) {
      setError(q.get('error') === 'access_denied' ? 'Google sign-in was cancelled.' : 'Google sign-in expired. Please try again.')
      return
    }
    api.post<AuthTokens>('/auth/google', { code, redirect_uri: googleRedirectUri(window.location.origin) })
      .then((res) => {
        setTokens(res.access_token, res.refresh_token)
        // Same-origin paths only, like the magic-code login.
        window.location.replace(from.startsWith('/') && !from.startsWith('//') ? from : '/home')
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : 'Google sign-in failed. Please try again.'))
  }, [])

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-text-primary">Signing you in</h1>
      {error ? (
        <>
          <p role="alert" className="text-sm text-status-error">{error}</p>
          <Link href="/login" className="text-sm text-text-secondary underline">Back to sign in</Link>
        </>
      ) : (
        <p role="status" className="text-sm text-text-secondary">Checking your Google account…</p>
      )}
    </div>
  )
}
