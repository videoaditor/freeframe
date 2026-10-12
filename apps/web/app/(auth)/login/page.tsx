'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { getAccessToken } from '@/lib/auth'
import { shouldBounceToGateEarly } from '@/lib/gate'
import { LoginForm } from '@/components/auth/login-form'
import type { SetupStatus } from '@/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
// Baked at build time (docker-compose.coolify.yml sets it "true"): when the gate
// is the login, a signed-out /login bounces straight to it with no intermediate
// API calls, so the page never dwells.
const OIDC_ENABLED = process.env.NEXT_PUBLIC_OIDC_ENABLED === 'true'

export default function LoginPage() {
  const router = useRouter()
  const [showForm, setShowForm] = useState(false)

  useEffect(() => {
    let active = true

    async function needsSetup(): Promise<boolean> {
      try {
        const status = await api.get<SetupStatus>('/setup/status')
        return status.needs_setup
      } catch {
        return false
      }
    }

    async function run() {
      const params = new URLSearchParams(window.location.search)

      // Already signed in: go straight to the destination, never paint /login.
      const token = getAccessToken()
      if (token) {
        document.cookie = `ff_access_token=${token}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`
        const from = params.get('from')
        router.replace(from && from.startsWith('/') && !from.startsWith('//') ? from : '/home')
        return
      }

      // Gate is the login: bounce straight to it, synchronously, with no API round
      // trips - so a signed-out /login never sits on screen (this is what caused
      // the ~1s "login page" flash on the way to the gate). A gate failure comes
      // back as ?error= (shouldBounceToGateEarly -> false) and the whop lane opts
      // out; both fall through to the form below instead of looping.
      const whop = document.cookie.includes('ff_auth_provider=whop')
      if (OIDC_ENABLED && shouldBounceToGateEarly(params) && !whop) {
        const from = params.get('from')
        const qp = from ? `?from=${encodeURIComponent(from)}` : ''
        window.location.assign(`${API_URL}/auth/oidc/login${qp}`)
        return
      }

      // Fallback (gate disabled, whop, or a gate error): show the sign-in form.
      // The first-time-setup check only matters on this path.
      if (await needsSetup()) {
        if (active) router.replace('/setup')
        return
      }
      if (active) setShowForm(true)
    }

    run()
    return () => { active = false }
  }, [router])

  // While we decide where to send the visitor (checking the session, bouncing to
  // the gate, or redirecting an already-signed-in user to their destination), the
  // branded (auth) layout shell (logo + card + tagline) would otherwise paint
  // behind us and flash as "the login page" - most visibly on the fresh full-page
  // load that follows a gate (Google) sign-in. Cover the viewport with the plain
  // app background so nothing branded shows until we either land on the
  // destination or have actually decided to show the sign-in form.
  if (!showForm) return <div aria-hidden className="fixed inset-0 z-50 bg-bg-primary" />
  return <LoginForm />
}
