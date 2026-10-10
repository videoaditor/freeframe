'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { getAccessToken } from '@/lib/auth'
import { shouldBounceToGateEarly } from '@/lib/gate'
import { LoginForm } from '@/components/auth/login-form'
import type { SetupStatus } from '@/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

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
      // Already signed in: go straight to the destination, never paint /login.
      const token = getAccessToken()
      if (token) {
        document.cookie = `ff_access_token=${token}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`
        const params = new URLSearchParams(window.location.search)
        const from = params.get('from')
        router.replace(from && from.startsWith('/') && !from.startsWith('//') ? from : '/home')
        return
      }

      if (await needsSetup()) {
        if (active) router.replace('/setup')
        return
      }

      const params = new URLSearchParams(window.location.search)
      if (!shouldBounceToGateEarly(params)) {
        if (active) setShowForm(true)
        return
      }

      try {
        const config = await api.get<{ enabled: boolean }>('/auth/oidc/config')
        if (config.enabled) {
          const from = params.get('from')
          const qp = from ? `?from=${encodeURIComponent(from)}` : ''
          window.location.assign(`${API_URL}/auth/oidc/login${qp}`)
          return
        }
      } catch {
        // Gate status unknown — fall through to the login form below.
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
