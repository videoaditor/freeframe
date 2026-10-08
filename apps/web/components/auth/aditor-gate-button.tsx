'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * Renders nothing until the API confirms the central gate (auth.aditor.ai) is
 * configured - keeps a self-hosted instance that hasn't registered with a
 * gate from showing a button whose click 404s.
 */
export function AditorGateButton() {
  const [enabled, setEnabled] = useState(false)

  useEffect(() => {
    api.get<{ enabled: boolean }>('/auth/oidc/config')
      .then((c) => setEnabled(!!c.enabled))
      .catch(() => {})
  }, [])

  if (!enabled) return null

  function start() {
    const from = new URLSearchParams(window.location.search).get('from') || ''
    const params = from ? `?from=${encodeURIComponent(from)}` : ''
    window.location.assign(`${API_URL}/auth/oidc/login${params}`)
  }

  return (
    <>
      <Button type="button" size="lg" onClick={start} className="mb-5 w-full">
        Sign in with Aditor
      </Button>
      <div className="mb-5 flex items-center gap-3 text-xs text-text-tertiary" aria-hidden="true">
        <span className="h-px flex-1 bg-border" />or<span className="h-px flex-1 bg-border" />
      </div>
    </>
  )
}
