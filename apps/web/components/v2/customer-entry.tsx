'use client'

import { useEffect, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import useSWR from 'swr'
import type { Project } from '@/types'
import { useAuthStore } from '@/stores/auth-store'
import { listRequests } from '@/lib/platform'
import { needsAutoReviewSetup } from '@/lib/onboarding'

/** Both Whop and email/Google enter /home. Do not interrupt editor deep links. */
export function CustomerEntry({ projects, children }: { projects?: Project[]; children: ReactNode }) {
  const user = useAuthStore(s => s.user)
  const router = useRouter()
  const { data: requests, error, mutate } = useSWR(user?.is_staff === false ? '/requests' : null, listRequests)
  const start = needsAutoReviewSetup(user, projects, requests)
  useEffect(() => { if (start) router.replace('/start') }, [start, router])
  if (user?.is_staff === false && error) return <div role="alert" className="p-8">Could not open your workspace. <button className="min-h-11 px-3 font-semibold text-accent" onClick={() => void mutate()}>Try again</button></div>
  if (user?.is_staff === false && (!requests || start)) return <p role="status" className="p-8 text-text-secondary">Opening AutoReview…</p>
  return <>{children}</>
}
