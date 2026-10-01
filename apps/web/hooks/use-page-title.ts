'use client'

import { useEffect } from 'react'

/**
 * Sets the browser tab title. Appends " – Autoreview" suffix.
 * Pass null/undefined to reset to default "Autoreview".
 */
export function usePageTitle(title: string | null | undefined) {
  useEffect(() => {
    document.title = title ? `${title} – Autoreview` : 'Autoreview'
    return () => { document.title = 'Autoreview' }
  }, [title])
}
