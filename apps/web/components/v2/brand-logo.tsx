'use client'

import * as React from 'react'
import useSWR from 'swr'
import { getBrandLogo, uploadBrandLogo } from '@/lib/platform'

/** Key the state to its project: switching brands must never carry a preview or error across. */
export function BrandLogo(props: { projectId: string; brandName: string }) {
  return <ProjectLogo key={props.projectId} {...props} />
}

function ProjectLogo({ projectId, brandName }: { projectId: string; brandName: string }) {
  const { data: logo, error: loadError, isLoading, mutate } = useSWR(
    `/projects/${projectId}/branding/logo`, () => getBrandLogo(projectId), { shouldRetryOnError: false },
  )
  const input = React.useRef<HTMLInputElement>(null)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState('')
  const [saved, setSaved] = React.useState(false)
  const inputId = React.useId()

  async function upload(file: File) {
    setError(''); setSaved(false)
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
      setError('Choose a PNG, JPG or WebP image.'); return
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('Choose an image under 5 MB.'); return
    }
    setBusy(true)
    try {
      const url = await uploadBrandLogo(projectId, file)
      await mutate(url, { revalidate: false })
      setSaved(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The logo did not save. Choose the file to try again.')
    } finally { setBusy(false) }
  }

  return (
    <section aria-label={`${brandName} brand logo`} className="rounded-2xl border border-border bg-bg-secondary p-4">
      <div className="flex items-start gap-4">
        <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border bg-bg-primary p-2">
          {logo ? (
            // Presigned project URLs are dynamic and expire; use the browser directly.
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logo} alt={`${brandName} logo`} className="h-full w-full object-contain" />
          ) : <span aria-hidden="true" className="text-[1.375rem] font-semibold text-text-secondary">{brandName.slice(0, 1).toUpperCase()}</span>}
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="break-words text-[0.9375rem] font-semibold text-text-primary">{brandName} logo</h2>
          <p className="mt-1 text-[0.8125rem] leading-relaxed text-text-secondary">Shown on this brand’s upload links. Saves automatically.</p>
          {isLoading ? <p role="status" className="mt-3 text-[0.8125rem] text-text-secondary">Loading logo…</p> : loadError ? (
            <div role="alert" className="mt-2 text-[0.8125rem] text-text-secondary">Could not load the logo. <button type="button" onClick={() => mutate()} className="press min-h-11 rounded-full px-3 font-semibold text-text-primary hover:bg-bg-hover">Retry</button></div>
          ) : (
            <>
              <label htmlFor={inputId} className="sr-only">Choose brand logo</label>
              <input ref={input} id={inputId} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" disabled={busy}
                onChange={e => { const file = e.target.files?.[0]; e.target.value = ''; if (file) void upload(file) }} />
              <button type="button" disabled={busy} onClick={() => input.current?.click()}
                className="press mt-3 min-h-11 rounded-full border border-border px-4 text-[0.8125rem] font-medium text-text-primary hover:bg-bg-hover disabled:cursor-wait disabled:opacity-60">
                {busy ? 'Saving logo…' : logo ? 'Change logo' : 'Upload logo'}
              </button>
              <p className="mt-2 text-[0.75rem] text-text-secondary">PNG, JPG or WebP · up to 5 MB</p>
            </>
          )}
          <p role="status" className="text-[0.8125rem] text-text-secondary">{saved ? 'Logo saved.' : ''}</p>
          {error && <p role="alert" className="mt-2 text-[0.8125rem] text-status-error">{error}</p>}
        </div>
      </div>
    </section>
  )
}
