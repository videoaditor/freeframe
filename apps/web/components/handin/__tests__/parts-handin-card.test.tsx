import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SWRConfig } from 'swr'
import { afterEach, expect, it, vi } from 'vitest'
import { PartsHandin } from '../parts-handin'
import { lookUpCard } from '@/lib/handin'
vi.mock('@/lib/iterations', () => ({ createPartHandin: vi.fn() }))
vi.mock('@/lib/handin', () => ({ lookUpCard: vi.fn() }))
// A staff editor holds no membership on "Test - Workspace": it must still be offered, as in the complete-ad hand-in.
vi.mock('@/lib/api', () => ({ api: { get: async () => [
  { id: 'ws-test', name: 'Test - Workspace', is_workspace: true, role: null },
  { id: 'ws-other', name: 'Other - Workspace', is_workspace: true, role: 'editor' },
  { id: 'card-project', name: 'Old card project', is_workspace: false, role: 'owner' },
] } }))
vi.mock('@/lib/platform', () => ({ viewRequest: async () => ({}) }))
vi.mock('@/stores/auth-store', () => ({ useAuthStore: (selector: any) => selector({ user: { is_staff: true } }) }))
vi.mock('../workspace-picker', () => ({ WorkspacePicker: ({ projects, value }: any) => <div><p>Selected: {value?.name ?? 'none'}</p><ul>{projects.map((p: any) => <li key={p.id}>{p.name}</li>)}</ul></div> }))
vi.mock('@/components/v2/parts-workspace', () => ({ PartsWorkspace: () => <div /> }))
afterEach(() => { cleanup(); vi.clearAllMocks() })

it('offers every brand workspace to staff and pre-selects the one matching the card', async () => {
  vi.mocked(lookUpCard).mockResolvedValue({ name: 'Test 1', brand: 'Test', hasBriefing: false })
  render(<SWRConfig value={{ provider: () => new Map() }}><PartsHandin /></SWRConfig>)
  expect(await screen.findByText('Test - Workspace')).toBeInTheDocument()
  expect(screen.getByText('Other - Workspace')).toBeInTheDocument()
  expect(screen.queryByText('Old card project')).not.toBeInTheDocument()
  const input = screen.getByLabelText('Trello card')
  fireEvent.change(input, { target: { value: 'https://trello.com/c/AbCd1234/1-test1' } })
  fireEvent.blur(input)
  await waitFor(() => expect(lookUpCard).toHaveBeenCalledWith('https://trello.com/c/AbCd1234/1-test1'))
  expect(await screen.findByTestId('card-confirmation')).toHaveTextContent('No briefing found on this card')
  expect(await screen.findByText('Selected: Test - Workspace')).toBeInTheDocument()
})
