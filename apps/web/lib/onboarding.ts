import type { Project, User } from '@/types'
import type { FileRequest } from './platform'
import { ownsProject } from './workspace-access'

export type SetupProgress = { version: 1; step: 'brand' | 'brief' | 'share' | 'done'; projectId?: string; requestId?: string }
export function setupProgress(user: User | null): SetupProgress | null {
  const value = user?.preferences?.autoreview_setup as Partial<SetupProgress> | undefined
  return value?.version === 1 && ['brand', 'brief', 'share', 'done'].includes(value.step || '') ? value as SetupProgress : null
}
export function canSetUpAutoReview(user: User | null, projects?: Project[]) {
  return !!user && user.is_staff === false && !!projects &&
    (projects.length === 0 || projects.some(p => ownsProject(user, p)))
}
export function needsAutoReviewSetup(user: User | null, projects?: Project[], requests?: FileRequest[]) {
  return canSetUpAutoReview(user, projects) && !!requests && requests.length === 0 && setupProgress(user)?.step !== 'done'
}
