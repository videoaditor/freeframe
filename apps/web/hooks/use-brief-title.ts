'use client'
import { useEffect, useRef, useCallback, type Dispatch, type SetStateAction } from 'react'
import { briefingFilePayload, briefingFilenameTitle, briefingLinkTitle } from '@/lib/briefing'
import { getAccessToken } from '@/lib/auth'
import { authHeaders } from '@/lib/auth-headers'

/** Never replace the name after the user has typed in it, even when a slow lookup finishes. */
export function useBriefTitle(file: File | null, text: string, setTitle: Dispatch<SetStateAction<string>>) {
  const manual = useRef(false)
  const reset = useCallback(() => { manual.current = false }, [])
  const edit = useCallback(() => { manual.current = true }, [])
  useEffect(() => {
    let cancelled = false
    const suggest = (value: string | null) => { if (value && !cancelled && !manual.current) setTitle(value) }
    if (file) {
      suggest(briefingFilenameTitle(file.name))
      if (/\.(md|markdown|txt)$/i.test(file.name)) void briefingFilePayload(file).then(p => {
        const heading = p.text?.match(/^\s*#{1,2}\s+(.+)$/m)?.[1]?.trim()
        if (heading) suggest(heading.slice(0, 255))
      }).catch(() => {})
    } else if (/^https?:\/\/\S+$/i.test(text.trim())) {
      const url = text.trim()
      suggest(briefingLinkTitle(url))
      const timer = setTimeout(() => {
        if (!/^https:\/\/docs\.google\.com\/document\/d\//.test(url) || manual.current) return
        void fetch('/brief-title', { method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders(getAccessToken()) }, body: JSON.stringify({ url }) })
          .then(r => r.ok ? r.json() : null).then(data => { if (typeof data?.title === 'string') suggest(data.title) }).catch(() => {})
      }, 400)
      return () => { cancelled = true; clearTimeout(timer) }
    }
    return () => { cancelled = true }
  }, [file, text, setTitle])
  return { edit, reset }
}
