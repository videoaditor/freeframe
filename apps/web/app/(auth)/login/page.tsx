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

  // Nothing paints here while a session cookie might still be present or the
  // gate redirect is in flight - only the destination (dashboard, gate, or the
  // login form itself) ever shows.
  if (!showForm) return null
  return <LoginForm />
}
