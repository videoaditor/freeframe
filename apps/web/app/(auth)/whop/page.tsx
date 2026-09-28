'use client'

import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { resetWhopEntry, setTokens } from '@/lib/auth'

export default function WhopPage() {
  const started = useRef(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(true)

  async function connect() {
    setBusy(true)
    setError(null)
    try {
      resetWhopEntry()
    } catch {
      setError('Allow browser storage for this app, then try again.')
      setBusy(false)
      return
    }
    try {
      const response = await fetch('/whop/session', { method: 'POST', cache: 'no-store' })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Whop sign-in is temporarily unavailable. Please try again.')
      if (typeof data.access_token !== 'string' || typeof data.refresh_token !== 'string') throw new Error('Sign-in could not be completed. Please try again.')
      try {
        setTokens(data.access_token, data.refresh_token, 'whop')
        if (!document.cookie.split(';').some((cookie) => cookie.trim().startsWith('ff_access_token='))) {
          throw new Error('Cookies unavailable')
        }
      } catch {
        throw new Error('Allow browser storage for this app, then try again.')
      }
      // A full navigation also discards any previous customer's in-memory stores.
      window.location.replace('/home')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Whop sign-in is temporarily unavailable. Please try again.')
      setBusy(false)
    }
  }

  useEffect(() => {
    if (started.current) return
    started.current = true
    void connect()
  }, [])

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-text-primary">Your Review workspace</h1>
      {busy ? (
        <p role="status" className="text-sm text-text-secondary">Opening your workspace…</p>
      ) : (
        <>
          <p role="alert" className="text-sm leading-relaxed text-text-secondary">{error}</p>
          <Button type="button" size="lg" onClick={() => void connect()} className="w-full">
            Try again
          </Button>
        </>
      )}
    </div>
  )
}
