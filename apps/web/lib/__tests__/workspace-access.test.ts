import { expect, it } from 'vitest'
import { canManageWorkspace } from '../workspace-access'
import type { Project, User } from '@/types'
it('distinguishes internal editors, external editors and customer owners', () => {
  const user = { id: 'editor', is_staff: true, is_superadmin: false } as User
  const project = { id: 'project', created_by: 'customer', role: 'editor' } as Project
  expect(canManageWorkspace(user, [project])).toBe(false)
  expect(canManageWorkspace({ ...user, is_staff: false }, [project])).toBe(false)
  expect(canManageWorkspace({ ...user, is_staff: false, id: 'customer' }, [project])).toBe(true)
  expect(canManageWorkspace(user, [{ ...project, role: 'owner' }])).toBe(true)
  expect(canManageWorkspace({ ...user, is_superadmin: true })).toBe(true)
})
