import type { Project, User } from '@/types'
/** UI visibility only; each management API also checks the selected project. */
export function ownsProject(user: User | null, project: Project) {
  return !!user && (user.is_superadmin || project.role === 'owner' || project.created_by === user.id)
}
export function canManageWorkspace(user: User | null, projects: Project[] = []) {
  return !!user && (user.is_superadmin || projects.some(p => ownsProject(user, p)))
}
