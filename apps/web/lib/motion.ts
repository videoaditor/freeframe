'use client'

import { useRouter } from 'next/navigation'
import { useCallback } from 'react'

/** Run a DOM change inside a View Transition when the browser has one; otherwise just run it. */
export function withViewTransition(fn: () => void) {
  const d = document as Document & { startViewTransition?: (cb: () => void) => unknown }
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  if (d.startViewTransition && !reduce) d.startViewTransition(fn)
  else fn()
}

/** router.push, crossfaded between screens (see ::view-transition-* in globals.css). */
export function useTransitionRouter() {
  const router = useRouter()
  const push = useCallback((href: string) => withViewTransition(() => router.push(href)), [router])
  const replace = useCallback((href: string) => withViewTransition(() => router.replace(href)), [router])
  return { push, replace, router }
}
