'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api, ApiError } from '@/lib/api'
import { setTokens } from '@/lib/auth'
import { useAuthStore } from '@/stores/auth-store'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { AditorGateButton } from '@/components/auth/aditor-gate-button'
import type { AuthTokens } from '@/types'

/** Where to land after signing in: the page that sent you here, else the v2 home. Same-origin paths only. */
function afterLogin(): string {
  const from = new URLSearchParams(window.location.search).get('from') || ''
  return from.startsWith('/') && !from.startsWith('//') ? from : '/home'
}

// Build-time flag: NEXT_PUBLIC_PASSWORD_LOGIN_ENABLED=false removes the password
// path from the UI entirely. Defaults to enabled so upstream behaviour is unchanged.

export function LoginForm() {
  const PASSWORD_LOGIN_ENABLED = process.env.NEXT_PUBLIC_PASSWORD_LOGIN_ENABLED !== 'false'
  // Break-glass only: the central gate (auth.aditor.ai) is the canonical, and only
  // intended, sign-in. Password stays off the page unless an operator explicitly
  // turns this on at build time, or this instance has no gate configured at all.
  const LEGACY_LOGIN_ENABLED = process.env.NEXT_PUBLIC_LEGACY_LOGIN_ENABLED === 'true'
  const [gateAvailable, setGateAvailable] = useState<boolean | null>(null)
  const router = useRouter()
  const legacyVisible = LEGACY_LOGIN_ENABLED || gateAvailable === false
  const showClassicForm = legacyVisible && PASSWORD_LOGIN_ENABLED
  const [generalError, setGeneralError] = useState('')
  const [loading, setLoading] = useState(false)

  // Classic login fields
  const [classicEmail, setClassicEmail] = useState('')
  const [classicPassword, setClassicPassword] = useState('')
  const [classicError, setClassicError] = useState('')

  // Surfaced by a server redirect back from /auth/oidc/callback (apps/api/routers/auth.py)
  // when the gate sign-in itself didn't go through - shown regardless of which
  // view renders, since which one that is depends on gate availability.
  useEffect(() => {
    const code = new URLSearchParams(window.location.search).get('error')
    if (!code) return
    const message = {
      gate_sign_in_failed: 'Gate sign-in failed. Please try again.',
      gate_sign_in_expired: 'Gate sign-in expired. Please try again.',
      not_registered: 'This account is not registered for Aditor Review yet. Ask an admin to add you.',
    }[code] || 'Sign-in failed. Please try again.'
    setGeneralError(message)
    setClassicError(message)
  }, [])

  // ─── Classic login ───────────────────────────────────────────────────────

  async function handleClassicLogin(e: React.FormEvent) {
    e.preventDefault()
    setClassicError('')

    if (!classicEmail || !classicPassword) {
      setClassicError('Email and password are required')
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(classicEmail)) {
      setClassicError('Enter a valid email address')
      return
    }

    setLoading(true)
    try {
      const res = await api.post<AuthTokens>('/auth/login', {
        email: classicEmail,
        password: classicPassword,
      })
      setTokens(res.access_token, res.refresh_token)
      await useAuthStore.getState().fetchUser()
      router.replace(afterLogin())
    } catch (err) {
      if (err instanceof ApiError) {
        setClassicError(err.detail)
      } else {
        setClassicError('Invalid email or password')
      }
    } finally {
      setLoading(false)
    }
  }

  // ─── Render ──────────────────────────────────────────────────────────────

  // The gate (auth.aditor.ai) is the canonical, and only, sign-in: show only its
  // button until either LEGACY_LOGIN_ENABLED breaks the glass or the gate isn't
  // configured on this instance.
  if (!showClassicForm) {
    return (
      <div className="animate-slide-up">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-text-primary mb-1">Sign in to AutoReview</h1>
        </div>
        <AditorGateButton onAvailabilityChange={setGateAvailable} showDivider={false} />
        {gateAvailable === null && <p role="status" className="text-sm text-text-secondary">Loading sign-in…</p>}
        {generalError && (
          <p role="alert" className="mt-4 text-sm text-status-error">{generalError}</p>
        )}
      </div>
    )
  }

  return (
    <div className="animate-slide-up">
      <div className="mb-8">
        <h1 className="text-xl font-semibold text-text-primary mb-1">Sign in with password</h1>
        <p className="text-sm text-text-secondary">Enter your email and password to continue.</p>
      </div>

      <AditorGateButton onAvailabilityChange={setGateAvailable} />

      <form onSubmit={handleClassicLogin} className="flex flex-col gap-4">
        {classicError && (
          <div className="rounded-md border border-status-error/30 bg-status-error/10 px-3 py-2.5 text-sm text-status-error">
            {classicError}
          </div>
        )}

        <Input
          label="Email address"
          type="email"
          placeholder="you@example.com"
          autoComplete="email"
          value={classicEmail}
          onChange={(e) => setClassicEmail(e.target.value)}
        />

        <Input
          label="Password"
          type="password"
          placeholder="Your password"
          autoComplete="current-password"
          value={classicPassword}
          onChange={(e) => setClassicPassword(e.target.value)}
        />

        <Button type="submit" size="lg" loading={loading} className="mt-2 w-full">
          Sign in
        </Button>
      </form>
    </div>
  )
}
