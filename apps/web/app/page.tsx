'use client'

/**
 * The front door (platform v2). WeTransfer-simple: one thing to do on this screen - drop a video.
 *
 * Signed in → straight to /home. Signed out → drop an ad, watch it upload, get the review in about a
 * minute against house best practice, no account. The end of that flow is the one invitation:
 * continue with your email to get your own rules and send request links to your editors.
 *
 * Spec: docs/superpowers/specs/2026-09-28-review-platform-v2-design.md.
 */
import * as React from 'react'
import Link from 'next/link'
import { ArrowRight, Inbox, ShieldCheck, Sparkles } from 'lucide-react'
import { getAccessToken } from '@/lib/auth'
import { useTransitionRouter, withViewTransition } from '@/lib/motion'
import { tryReview, TryError, type ReviewComment } from '@/lib/platform'
import { GATE_BASE } from '@/lib/handin'
import { DropZone } from '@/components/v2/drop-zone'
import { UploadCard, type UploadPhase } from '@/components/v2/upload-card'
import { ReviewList } from '@/components/v2/review-list'

type State =
  | { step: 'idle' }
  | { step: 'working'; file: File; progress: number; phase: UploadPhase; error?: string }
  | { step: 'result'; file: File; comments: ReviewComment[]; left: number }

export default function FrontDoor() {
  const { replace, push } = useTransitionRouter()
  const [state, setState] = React.useState<State>({ step: 'idle' })
  const [email, setEmail] = React.useState('')
  const videoRef = React.useRef<HTMLVideoElement>(null)
  const [preview, setPreview] = React.useState<string | null>(null)

  React.useEffect(() => { if (getAccessToken()) replace('/home') }, [replace])
  React.useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])

  const run = React.useCallback(async (file: File) => {
    setPreview((old) => { if (old) URL.revokeObjectURL(old); return URL.createObjectURL(file) })
    withViewTransition(() => setState({ step: 'working', file, progress: 0, phase: 'uploading' }))
    try {
      const r = await tryReview(file, (p) => setState((s) => s.step === 'working' ? { ...s, progress: p, phase: p >= 1 ? 'reviewing' : 'uploading' } : s))
      withViewTransition(() => setState({ step: 'result', file, comments: r.comments, left: r.left }))
    } catch (e) {
      const msg = e instanceof TryError ? e.message : 'The upload stopped. Drop the file again.'
      setState({ step: 'working', file, progress: 0, phase: 'error', error: msg })
    }
  }, [])

  const seek = (t: number) => {
    const v = videoRef.current
    if (!v) return
    v.currentTime = t
    v.play().catch(() => {})
  }

  const continueWithEmail = (e: React.FormEvent) => {
    e.preventDefault()
    push(`/login?from=/home${email ? `&email=${encodeURIComponent(email)}` : ''}`)
  }

  return (
    <div className="min-h-screen bg-bg-primary">
      <div className="orange-halo pointer-events-none absolute inset-x-0 top-0 h-[520px]" aria-hidden="true" />
      <header className="relative mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5" aria-label="Aditor Review">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/aditor-logo.png" alt="" className="h-7 w-7" />
          <span className="text-[15px] font-semibold tracking-tight text-text-primary">Aditor Review</span>
        </Link>
        <Link href="/login?from=/home" className="press inline-flex h-11 items-center rounded-full px-4 text-[15px] font-medium text-text-primary hover:bg-bg-hover">
          Sign in
        </Link>
      </header>

      <main className="relative mx-auto max-w-6xl px-4 pb-24 sm:px-6">
        {state.step !== 'result' && (
          <section className="page-in mx-auto max-w-2xl pt-10 text-center sm:pt-16">
            <h1 className="text-balance text-[34px] font-bold leading-[1.1] tracking-[-0.02em] text-text-primary sm:text-[52px]">
              Drop an ad.<br />Get feedback in a minute.
            </h1>
            <p className="mx-auto mt-4 max-w-md text-balance text-[17px] leading-relaxed text-text-secondary">
              Like WeTransfer, with a reviewer built in. Free, no account.
            </p>
            <div className="mt-10 text-left">
              {state.step === 'idle' ? (
                <DropZone
                  onFiles={([f]) => run(f)}
                  disabled={!GATE_BASE}
                  title="Drop a video"
                  hint={GATE_BASE ? 'or click to choose · MP4 or MOV · up to 3 min' : 'Free reviews are switched off on this server.'}
                />
              ) : (
                <UploadCard
                  file={state.file}
                  name={state.file.name}
                  size={state.file.size}
                  progress={state.progress}
                  phase={state.phase}
                  error={state.error}
                  onRetry={() => run(state.file)}
                  onRemove={() => setState({ step: 'idle' })}
                  className="sheet-in"
                />
              )}
            </div>
          </section>
        )}

        {state.step === 'result' && (
          <section className="page-in pt-6 sm:pt-10">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-[13px] font-medium uppercase tracking-[0.06em] text-accent">Review ready</p>
                <h1 className="mt-1 text-[28px] font-bold tracking-[-0.02em] text-text-primary sm:text-[34px]">{state.file.name}</h1>
              </div>
              <button type="button" onClick={() => withViewTransition(() => setState({ step: 'idle' }))} className="press inline-flex h-11 items-center rounded-full border border-border px-5 text-[15px] font-medium text-text-primary hover:bg-bg-hover">
                Review another
              </button>
            </div>
            <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
              <div className="lg:sticky lg:top-6 lg:self-start">
                {preview && (
                  <video ref={videoRef} src={preview} controls playsInline className="aspect-[9/16] max-h-[70vh] w-full rounded-[var(--radius-xl)] bg-black object-contain" />
                )}
              </div>
              <div>
                <ReviewList comments={state.comments} onSeek={seek} />
                <form onSubmit={continueWithEmail} className="glass mt-10 p-6 sm:p-7">
                  <h2 className="text-[22px] font-semibold tracking-tight text-text-primary">Want this for your brand?</h2>
                  <p className="mt-2 text-[15px] leading-relaxed text-text-secondary">
                    Add your own rules, send a request link to your editors, and see their work only once it is clean.
                  </p>
                  <div className="mt-5 flex flex-col gap-3 sm:flex-row">
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@brand.com"
                      autoComplete="email"
                      aria-label="Your email"
                      className="h-12 flex-1 rounded-full border border-border bg-bg-primary px-5 text-[17px] text-text-primary outline-none placeholder:text-text-tertiary focus:border-accent"
                    />
                    <button type="submit" className="press inline-flex h-12 items-center justify-center gap-2 rounded-full bg-accent px-6 text-[17px] font-semibold text-text-inverse hover:bg-accent-hover">
                      Continue <ArrowRight className="h-4 w-4" />
                    </button>
                  </div>
                  <p className="mt-3 text-[13px] text-text-tertiary">
                    We email you a 6-digit code. No password. {state.left > 0 ? `${state.left} free ${state.left === 1 ? 'review' : 'reviews'} left today.` : ''}
                  </p>
                </form>
              </div>
            </div>
          </section>
        )}

        {state.step === 'idle' && (
          <section className="mx-auto mt-20 grid max-w-4xl gap-4 sm:grid-cols-3" aria-label="How it works">
            {[
              { icon: Inbox, title: 'Request files', body: 'Drop your briefing, get a link. Send it to your editor.' },
              { icon: Sparkles, title: 'Instant review', body: 'Every upload is checked against your briefing, your brand, and best practice.' },
              { icon: ShieldCheck, title: 'Only clean work reaches you', body: 'Must-fixes go back to the editor first. Small notes never hold anything up.' },
            ].map(({ icon: Icon, title, body }) => (
              <div key={title} className="rounded-[var(--radius-xl)] border border-border bg-bg-secondary/60 p-5">
                <Icon className="h-5 w-5 text-accent" strokeWidth={1.75} />
                <h2 className="mt-3 text-[17px] font-semibold tracking-tight text-text-primary">{title}</h2>
                <p className="mt-1.5 text-[15px] leading-relaxed text-text-secondary">{body}</p>
              </div>
            ))}
          </section>
        )}
      </main>
    </div>
  )
}
