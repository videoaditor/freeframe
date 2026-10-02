import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { SWRConfig } from 'swr'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import ProjectsPage from '../page'
import { api } from '@/lib/api'

const state = vi.hoisted(() => ({ user: { id: 'owner', is_staff: false }, isSuperAdmin: false, push: vi.fn() }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: state.push }) }))
vi.mock('@/stores/auth-store', () => ({ useAuthStore: () => state }))
vi.mock('@/hooks/use-page-title', () => ({ usePageTitle: () => {} }))
vi.mock('@/lib/api', () => ({ api: { get: vi.fn() } }))
vi.mock('@/components/projects/project-card', () => ({ ProjectCard: ({ project }: { project: { id: string; name: string } }) => <a href={`/projects/${project.id}`}>{project.name}</a> }))
vi.mock('@/components/v2/request-sheet', () => ({ RequestSheet: ({ open, onCreated }: { open: boolean; onCreated: () => void }) => open ? <div role="dialog" aria-label="Request files"><button onClick={onCreated}>Created</button></div> : null }))
afterEach(cleanup)
beforeEach(() => {
  vi.resetAllMocks()
  state.user.is_staff = false
  state.isSuperAdmin = false
  vi.mocked(api.get).mockResolvedValue([])
})
function mount() {
  render(<SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0, shouldRetryOnError: false }}><ProjectsPage /></SWRConfig>)
}
it('guides a customer to their own file request instead of staff hand-in', async () => {
  mount()
  await screen.findByText('No projects yet')
  expect(screen.queryByText(/Trello/)).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Upload' })).not.toBeInTheDocument()
  fireEvent.click(screen.getAllByRole('button', { name: 'Request files' })[0])
  expect(screen.getByRole('dialog', { name: 'Request files' })).toBeInTheDocument()
  expect(state.push).not.toHaveBeenCalled()
  vi.mocked(api.get).mockResolvedValue([{ id: 'new', name: 'New brand', created_by: 'owner', is_workspace: true }])
  fireEvent.click(screen.getByRole('button', { name: 'Created' }))
  await screen.findByRole('link', { name: 'New brand' })
})
it('shows all authorized customer projects, including existing non-workspace projects', async () => {
  vi.mocked(api.get).mockResolvedValue([
    { id: 'brand', name: 'Brand workspace', created_by: 'owner', is_workspace: true },
    { id: 'old', name: 'Existing project', created_by: 'owner', is_workspace: false },
    { id: 'shared', name: 'Shared brand', created_by: 'other', is_workspace: false, role: 'reviewer' },
  ])
  mount()
  await screen.findByRole('link', { name: 'Existing project' })
  expect(screen.getByRole('link', { name: 'Shared brand' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Brand workspace' })).toBeInTheDocument()
  expect(screen.getByText('3 projects')).toBeInTheDocument()
})
it('keeps the staff workspace-only view and Trello hand-in action', async () => {
  state.user.is_staff = true
  vi.mocked(api.get).mockResolvedValue([
    { id: 'brand', name: 'Staff workspace', is_workspace: true },
    { id: 'stray', name: 'Old per-card project', created_by: 'owner', is_workspace: false },
  ])
  mount()
  await screen.findByRole('link', { name: 'Staff workspace' })
  expect(screen.queryByRole('link', { name: 'Old per-card project' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Upload' }))
  expect(state.push).toHaveBeenCalledWith('/handin')
})
it('distinguishes a failed project fetch from an empty customer account', async () => {
  vi.mocked(api.get).mockRejectedValue(new Error('Network unavailable'))
  mount()
  await screen.findByText('Unable to load projects. Try again.')
  expect(screen.queryByText('No projects yet')).not.toBeInTheDocument()
  vi.mocked(api.get).mockResolvedValue([])
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
  await screen.findByText('No projects yet')
})
