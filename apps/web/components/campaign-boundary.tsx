'use client'

import { useEffect, useState, type ReactNode } from 'react'
import useSWR from 'swr'
import { X } from 'lucide-react'
import { useAuthStore } from '@/stores/auth-store'
import { api } from '@/lib/api'
import { ProductFeedback } from './product-feedback'

type CampaignStatus = { reviewedAds: number; recommendedPlan: 'team' | 'masterclass' }
const plans = [
  { id: 'masterclass', name: 'Masterclass + Tools', href: 'https://whop.com/checkout/plan_tWfZVey4GvWhl',
    description: 'Keep reviewing and learn the wider workflow with the included training and tools.' },
  { id: 'team', name: 'Team', href: 'https://whop.com/checkout/plan_lm63pw8rtX7uk',
    description: 'Bring your editors into the workflow when you have a steady stream of ads to review.' },
] as const

export function CampaignBoundary({ children }: { children: ReactNode }) {
  const { user } = useAuthStore()
  const campaign = user?.suite_campaign
  const [now, setNow] = useState(() => Date.now())
  const { data, error } = useSWR<CampaignStatus>(campaign?.previewOnly ? '/auth/campaign' : null,
    () => api.get<CampaignStatus>('/auth/campaign'), { refreshInterval: 60000, shouldRetryOnError: false })
  useEffect(() => {
    if (!campaign?.previewOnly) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [campaign?.previewOnly])

  if (!campaign?.previewOnly) return <>{children}</>
  const expired = campaign.state === 'expired' || now >= Date.parse(campaign.endsAt)
  if (!expired) return <>
    <PreviewNotice key={`${user?.id}:${campaign.id}:${campaign.endsAt}`} storageKey={`autoreview:preview-notice:${user?.id}:${campaign.id}:${campaign.endsAt}`} />
    {children}
  </>

  const recommended = data?.recommendedPlan
  return <section className="mx-auto w-full max-w-4xl px-4 py-10 sm:px-8 sm:py-16" aria-labelledby="preview-ended">
    <p className="text-sm font-semibold text-text-secondary">Telehealth preview · October 2026</p>
    <h1 id="preview-ended" className="mt-3 text-[2.125rem] font-semibold leading-tight tracking-tight">Your preview has ended</h1>
    <p className="mt-4 max-w-2xl text-base leading-relaxed text-text-secondary">Your brand rules and work are saved. Choose a plan to continue reviewing. You have not been charged.</p>
    <div className="mt-6 min-h-12 text-sm text-text-secondary" role="status">
      {data ? <><p>{data.reviewedAds} distinct ads successfully reviewed during your preview.</p>
        <p className="mt-1 font-medium text-text-primary">Recommended for your usage: {recommended === 'team' ? 'Team' : 'Masterclass + Tools'}</p></>
        : <p>{error ? 'Your usage is temporarily unavailable. You can still explore either plan.' : 'Checking your usage…'}</p>}
    </div>
    <div className="mt-6 grid gap-4 sm:grid-cols-2">
      {[...plans].sort((a, b) => Number(b.id === recommended) - Number(a.id === recommended)).map(plan => <article key={plan.id} className="flex flex-col rounded-2xl border border-border bg-bg-secondary p-6">
        <h2 className="text-xl font-semibold">{plan.name}</h2>
        <p className="mt-3 flex-1 text-base leading-relaxed text-text-secondary">{plan.description}</p>
        <a href={plan.href} target="_blank" rel="noopener noreferrer" className={`press mt-6 inline-flex min-h-11 items-center justify-center rounded-xl px-4 py-3 text-center font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 ${recommended === plan.id ? 'bg-accent text-text-inverse hover:bg-accent-hover' : 'border border-border text-text-primary hover:bg-bg-tertiary'}`}>
          Explore {plan.name}
        </a>
      </article>)}
    </div>
    <p className="mt-4 text-sm text-text-secondary">Review pricing and terms on Whop before choosing a plan. After upgrading, reopen AutoReview from Whop.</p>
    <div className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6">
      <p className="text-sm text-text-secondary">Something we could improve? We still want to hear it.</p><ProductFeedback />
    </div>
  </section>
}


function PreviewNotice({ storageKey }: { storageKey: string }) {
  const [dismissed, setDismissed] = useState<boolean | null>(null)

  useEffect(() => {
    try { setDismissed(localStorage.getItem(storageKey) === 'dismissed') }
    catch { setDismissed(false) }
  }, [storageKey])

  function dismiss() {
    setDismissed(true)
    try { localStorage.setItem(storageKey, 'dismissed') }
    catch { /* Storage can be blocked; dismissal still works for this visit. */ }
  }

  if (dismissed === null) return null
  return <>
    {!dismissed && <aside aria-label="Preview access notice" className="campaign-preview-notice flex items-start justify-between gap-3 border-b px-4 py-3 sm:items-center sm:px-8">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">Telehealth preview</p>
        <p className="mt-1 text-sm leading-5">Free through October 31 · ends November 1, 12:00 am Eastern. One brand. No automatic charge.</p>
      </div>
      <button type="button" onClick={dismiss} aria-label="Dismiss preview notice" title="Dismiss preview notice" className="campaign-preview-dismiss flex h-11 w-11 shrink-0 items-center justify-center rounded-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-current active:opacity-70">
        <X size={18} aria-hidden="true" />
      </button>
    </aside>}
    <div className="fixed bottom-4 right-4 z-30 rounded-full border border-border bg-bg-elevated shadow-sm"><ProductFeedback /></div>
  </>
}
