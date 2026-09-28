'use client'

/**
 * A file request, from the editor's side. No account: the link is the permission.
 *
 * Goal of the screen: hand in the cut and know, within a minute, whether it is done. Name + email
 * once (remembered), drop the files, watch them upload, read the review. If something must be
 * fixed, the answer is on the same screen: drop the new version here, same file name.
 */
import * as React from 'react'
import useSWR from 'swr'
import { CheckCircle2, FileVideo } from 'lucide-react'
import { objectToNote, requestReview, uploadToRequest, viewRequest, type RequestReview } from '@/lib/platform'
import { withViewTransition } from '@/lib/motion'
import { DropZone } from '@/components/v2/drop-zone'
import { UploadCard, type UploadPhase } from '@/components/v2/upload-card'
import { ReviewList } from '@/components/v2/review-list'
import { ReviewWaiting } from '@/components/v2/review-waiting'
import { cn } from '@/lib/utils'

interface Job { id: string; file: File; progress: number; phase: UploadPhase; error?: string; assetId?: string }

const WHO_KEY = 'aditor-request-who'

function loadWho(): { name: string; email: string } {
  try { return JSON.parse(localStorage.getItem(WHO_KEY) || '') } catch { return { name: '', email: '' } }
}

export default function RequestPage({ params }: { params: { token: string } }) {
  const { token } = params
  const { data: view, error: viewError } = useSWR(`/r/${token}`, () => viewRequest(token), { shouldRetryOnError: false })
  const [jobs, setJobs] = React.useState<Job[]>([])
  const [who, setWho] = React.useState({ name: '', email: '' })
  const [whoError, setWhoError] = React.useState('')
  const nameRef = React.useRef<HTMLInputElement>(null)
  const previews = React.useRef<Record<string, string>>({})
  const videoRefs = React.useRef<Record<string, HTMLVideoElement | null>>({})

  React.useEffect(() => { setWho(loadWho()) }, [])

  const handedIn = (view?.assets.length || 0) > 0 || jobs.some((j) => j.phase !== 'error')
  const { data: review, mutate: refreshReview } = useSWR<RequestReview>(handedIn ? `/r/${token}/review` : null, () => requestReview(token), {
    refreshInterval: (d) => (!d || d.gate.status !== 'clear' || d.assets.some((a) => a.processing !== 'ready')) ? 5000 : 0,
  })

  const update = (id: string, patch: Partial<Job>) => setJobs((js) => js.map((j) => (j.id === id ? { ...j, ...patch } : j)))

  const upload = async (job: Job) => {
    update(job.id, { phase: 'uploading', progress: 0, error: undefined })
    try {
      const r = await uploadToRequest(token, who, job.file, (p) => update(job.id, { progress: p }))
      previews.current[r.asset_id] = URL.createObjectURL(job.file)
      update(job.id, { phase: 'done', progress: 1, assetId: r.asset_id })
      refreshReview()
    } catch (e) {
      update(job.id, { phase: 'error', error: e instanceof Error ? e.message : 'The upload stopped. Try again.' })
    }
  }

  const onFiles = async (files: File[]) => {
    if (!who.name.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(who.email)) {
      setWhoError('Add your name and email first, so the owner knows who handed this in.')
      nameRef.current?.focus()
      return
    }
    setWhoError('')
    try { localStorage.setItem(WHO_KEY, JSON.stringify(who)) } catch { /* private window */ }
    const fresh = files.map((file) => ({ id: `${file.name}-${file.size}-${Date.now()}`, file, progress: 0, phase: 'uploading' as UploadPhase }))
    withViewTransition(() => setJobs((js) => [...fresh, ...js]))
    // One at a time: a laptop uplink shared by three files finishes none of them sooner.
    for (const j of fresh) await upload(j)
  }

  const seek = (assetId: string, t: number) => {
    const v = videoRefs.current[assetId]
    if (v) { v.currentTime = t; v.play().catch(() => {}) }
  }

  if (viewError) {
    const status = (viewError as { status?: number }).status
    return (
      <Shell>
        <div className="page-in mx-auto max-w-md pt-24 text-center">
          <h1 className="text-[28px] font-bold tracking-tight text-text-primary">{status === 410 ? 'This link is closed' : 'This link does not work'}</h1>
          <p className="mt-3 text-[17px] text-text-secondary">{(viewError as Error).message} Ask whoever sent it for a new one.</p>
        </div>
      </Shell>
    )
  }
  if (!view) {
    return <Shell><div className="mx-auto max-w-2xl pt-16"><div className="skeleton-shimmer h-40 animate-shimmer rounded-[var(--radius-xl)]" /></div></Shell>
  }

  const gate = review?.gate
  const uploading = jobs.some((j) => j.phase === 'uploading')

  return (
    <Shell brand={view.brand} logo={view.logo_url}>
      <div className="page-in mx-auto w-full max-w-3xl pb-24 pt-8 sm:pt-12">
        <h1 className="text-balance text-[34px] font-bold leading-tight tracking-[-0.02em] text-text-primary">{view.title}</h1>
        {view.brief_excerpt && (
          <p className="mt-3 line-clamp-3 max-w-2xl text-[15px] leading-relaxed text-text-secondary">{view.brief_excerpt}</p>
        )}

        {gate && handedIn && !uploading && <GateBanner status={gate.status} open={gate.open_must_fixes} brand={view.brand} />}

        <div className="mt-8 grid gap-3 sm:grid-cols-2">
          <input ref={nameRef} value={who.name} onChange={(e) => setWho({ ...who, name: e.target.value })} placeholder="Your name" autoComplete="name" aria-label="Your name" className="field" />
          <input value={who.email} onChange={(e) => setWho({ ...who, email: e.target.value })} placeholder="Your email" type="email" autoComplete="email" aria-label="Your email" className="field" />
        </div>
        {whoError && <p className="mt-2 text-[13px] text-status-error" role="alert">{whoError}</p>}

        <div className="mt-4">
          <DropZone
            multiple
            accept="video/*,image/*"
            compact={handedIn}
            onFiles={onFiles}
            title={gate?.status === 'held' ? 'Drop the fixed version' : handedIn ? 'Add more files' : 'Drop your files'}
            hint={gate?.status === 'held' ? 'Same file name as before, so it becomes v2' : 'Videos or images · as many as you like'}
          />
        </div>

        {jobs.filter((j) => j.phase !== 'done').length > 0 && (
          <div className="mt-6 space-y-3">
            {jobs.filter((j) => j.phase !== 'done').map((j) => (
              <UploadCard key={j.id} file={j.file} name={j.file.name} size={j.file.size} progress={j.progress} phase={j.phase} error={j.error}
                onRetry={() => upload(j)} onRemove={() => setJobs((js) => js.filter((x) => x.id !== j.id))} className="sheet-in" />
            ))}
          </div>
        )}

        {review && review.assets.length > 0 && (
          <div className="mt-12 space-y-12">
            {review.assets.map((a) => {
              const pending = a.processing !== 'ready' || (gate?.status === 'reviewing' && !a.comments.length)
              const src = previews.current[a.asset_id]
              return (
                <article key={a.asset_id} className="fade-in">
                  <div className="mb-4 flex items-center gap-3">
                    <FileVideo className="h-5 w-5 text-text-tertiary" />
                    <h2 className="min-w-0 flex-1 truncate text-[20px] font-semibold tracking-tight text-text-primary">{a.name}</h2>
                    {a.version > 1 && <span className="rounded-full bg-bg-hover px-2.5 py-1 text-[12px] font-medium text-text-secondary">v{a.version}</span>}
                  </div>
                  <div className={cn('grid gap-6', src && 'md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]')}>
                    {src && (
                      <video ref={(el) => { videoRefs.current[a.asset_id] = el }} src={src} controls playsInline
                        className="aspect-[9/16] max-h-[60vh] w-full rounded-[var(--radius-xl)] bg-black object-contain md:sticky md:top-6" />
                    )}
                    {pending ? (
                      <p role="status" className="py-5 text-[15px] text-text-secondary">Feedback will appear here when the review is ready.</p>
                    ) : (
                      <ReviewList comments={a.comments} onSeek={src ? (t) => seek(a.asset_id, t) : undefined}
                        onObject={async (c, text) => {
                          const r = await objectToNote(token, { asset_id: a.asset_id, comment_id: c.id, body: c.body, text, name: who.name })
                          refreshReview()
                          return r
                        }} />
                    )}
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </div>
    </Shell>
  )
}

function GateBanner({ status, open, brand }: { status: 'reviewing' | 'held' | 'clear'; open: number; brand: string }) {
  if (status === 'clear') {
    return (
      <div className="glass fade-in mt-8 flex items-center gap-3 p-5" role="status">
        <CheckCircle2 className="h-6 w-6 shrink-0 text-status-success" />
        <p className="text-[17px] text-text-primary"><span className="font-semibold">All clear.</span> {brand} can see your work now. Anything below is optional.</p>
      </div>
    )
  }
  if (status === 'held') {
    return (
      <div className="mustfix-ring fade-in mt-8 bg-bg-secondary p-5" role="status">
        <p className="text-[17px] text-text-primary">
          <span className="font-semibold">{open} {open === 1 ? 'thing needs' : 'things need'} fixing before {brand} sees this.</span>{' '}
          Fix {open === 1 ? 'it' : 'them'} and drop the new version below with the same file name. If a note is wrong, tap Not right? under it.
        </p>
      </div>
    )
  }
  return (
    <div className="glass mt-8"><ReviewWaiting compact /></div>
  )
}

/**
 * White-label: this page belongs to the BRAND, not to us. Its logo (uploaded under Brand rules), or
 * its name set as a wordmark when there is none. No Aditor logo, no Aditor headline.
 */
function Shell({ children, brand, logo }: { children: React.ReactNode; brand?: string; logo?: string | null }) {
  return (
    <div className="min-h-screen bg-bg-primary">
      <div className="orange-halo pointer-events-none absolute inset-x-0 top-0 h-[420px]" aria-hidden="true" />
      <header className="relative mx-auto flex h-20 max-w-5xl items-center px-4 sm:px-6">
        {logo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={logo} alt={brand || ''} className="h-9 max-w-[180px] object-contain fade-in" />
        ) : brand ? (
          <span className="text-[20px] font-bold tracking-tight text-text-primary">{brand}</span>
        ) : null}
      </header>
      <main className="relative mx-auto max-w-5xl px-4 sm:px-6">{children}</main>
    </div>
  )
}
