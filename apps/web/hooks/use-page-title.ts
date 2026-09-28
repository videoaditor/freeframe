'use client'

import { useEffect } from 'react'

/**
 * Sets the browser tab title. Appends " – Aditor Review" suffix.
 * Pass null/undefined to reset to default "Aditor Review".
 */
export function usePageTitle(title: string | null | undefined) {
  useEffect(() => {
    document.title = title ? `${title} – Aditor Review` : 'Aditor Review'
    return () => { document.title = 'Aditor Review' }
  }, [title])
}
