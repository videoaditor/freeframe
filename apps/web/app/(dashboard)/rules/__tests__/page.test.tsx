import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { SWRConfig } from 'swr'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import RulesPage from '../page'
import { api } from '@/lib/api'
import { decideSuggestion, getRules, importRules } from '@/lib/platform'
import { ToastProvider } from '@/components/shared/toast'

vi.mock('@/lib/api', () => ({ api: { get: vi.fn() } }))
vi.mock('@/lib/platform', async importOriginal => ({ ...await importOriginal<typeof import('@/lib/platform')>(), getRules: vi.fn(), importRules: vi.fn(), decideSuggestion: vi.fn() }))
vi.mock('@/components/v2/brand-logo', () => ({ BrandLogo: () => null }))
vi.mock('@/hooks/use-page-title', () => ({ usePageTitle: vi.fn() }))
vi.mock('@/stores/auth-store', () => ({ useAuthStore: (selector: (s: unknown) => unknown) => selector({ user: { is_staff: false } }) }))

const longText = 'Keep the product name readable and inside the safe area. '.repeat(10) + '\nNever crop the closing disclaimer.'
const fixture = () => ({ brand: 'northline', rules: [
  { id: '1', name: 'Protect the logo', what: longText, scope: 'brand', severity: 'blocker', active: true },
  { id: '2', name: 'Let the product breathe', what: 'Keep backgrounds quiet.', scope: 'brand', severity: 'warning', active: true },
  { id: '3', name: 'Hidden old rule', what: '', scope: 'brand', severity: 'blocker', active: false },
  { id: '4', name: 'Keep speech clear', what: 'Voice should be audible over music.', scope: 'global', severity: 'warning', active: true },
], suggestions: [{ id: 's1', name: 'Hold the end card', what: 'Show the closing card for two seconds.', source: 'owner-comment' }] })
afterEach(cleanup)
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(api.get).mockResolvedValue([{ id: 'p1', name: 'Northline' }, { id: 'p2', name: 'Sunday Studio' }])
  vi.mocked(getRules).mockImplementation(async id => id === 'p1' ? fixture() : { brand: 'sunday', rules: [], suggestions: [] })
  vi.mocked(importRules).mockResolvedValue({ drafted: 1, found: 1 })
  vi.mocked(decideSuggestion).mockResolvedValue({ ok: true })
})
function mount() { return render(<SWRConfig value={{ provider: () => new Map(), shouldRetryOnError: false, dedupingInterval: 0 }}><ToastProvider><RulesPage /></ToastProvider></SWRConfig>) }
async function openImport() {
  await screen.findByRole('textbox', { name: 'Quick rule' })
}

it('shows active brand rules and exposes complete long guidance in an accessible sheet', async () => {
  mount()
  fireEvent.click(await screen.findByRole('button', { name: 'View rule: Protect the logo' }))
  const dialog = screen.getByRole('dialog')
  expect(dialog).toHaveTextContent('Never crop the closing disclaimer.')
  expect(within(dialog).getByText('Must follow')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Hidden old rule/ })).not.toBeInTheDocument()
  fireEvent.keyDown(dialog, { key: 'Escape' })
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByText('2 active rules · 1 must follow')).toBeInTheDocument()
})

it('groups by severity and searches rule content without losing the full library', async () => {
  mount()
  await screen.findByRole('button', { name: 'View rule: Protect the logo' })
  expect(within(screen.getByRole('region', { name: 'Must follow rules' })).getByRole('button', { name: 'View rule: Protect the logo' })).toBeInTheDocument()
  expect(within(screen.getByRole('region', { name: 'Guidance rules' })).getByRole('button', { name: 'View rule: Let the product breathe' })).toBeInTheDocument()
  fireEvent.change(screen.getByRole('textbox', { name: 'Search rules' }), { target: { value: 'no match' } })
  expect(screen.getByText('No matching rules')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Clear search' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Search rules' }), { target: { value: 'safe area' } })
  expect(screen.getByRole('button', { name: 'View rule: Protect the logo' })).toBeInTheDocument()
})

it('shows retry on a rules failure, not a false empty playbook', async () => {
  vi.mocked(getRules).mockRejectedValue(new Error('offline'))
  mount()
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not load rules')
  expect(screen.queryByText(/Make it unmistakably/)).not.toBeInTheDocument()
})

it('retains failed suggestions for retry and applies only a confirmed decision', async () => {
  vi.mocked(decideSuggestion).mockRejectedValueOnce(new Error('Could not save this rule.'))
  mount()
  fireEvent.click(await screen.findByText('For your approval'))
  fireEvent.click(screen.getByRole('button', { name: 'Use rule: Hold the end card' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not save this rule')
  expect(screen.getByText('Hold the end card')).toBeInTheDocument()
  vi.mocked(getRules).mockResolvedValue({ ...fixture(), suggestions: [] })
  fireEvent.click(screen.getByRole('button', { name: 'Use rule: Hold the end card' }))
  await waitFor(() => expect(screen.queryByText('Hold the end card')).not.toBeInTheDocument())
  expect(decideSuggestion).toHaveBeenLastCalledWith({ project_id: 'p1', suggestion_id: 's1', action: 'accept' })
})

it('keeps text after a failed import and sends a URL with the right project', async () => {
  vi.mocked(importRules).mockRejectedValueOnce(new Error('Could not read this guide.'))
  mount(); await openImport()
  fireEvent.change(screen.getByRole('textbox', { name: 'Quick rule' }), { target: { value: 'https://example.test/guide' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add for approval' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not read this guide')
  expect(screen.getByRole('textbox', { name: 'Quick rule' })).toHaveValue('https://example.test/guide')
  fireEvent.click(screen.getByRole('button', { name: 'Add for approval' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(importRules).toHaveBeenLastCalledWith({ project_id: 'p1', url: 'https://example.test/guide' })
})

it('isolates late imports and rule dialogs when the brand changes', async () => {
  let finish!: (value: { drafted: number; found: number }) => void
  vi.mocked(importRules).mockImplementation(() => new Promise(resolve => { finish = resolve }))
  mount(); await openImport()
  fireEvent.change(screen.getByRole('textbox', { name: 'Quick rule' }), { target: { value: 'Keep the logo visible.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add for approval' }))
  expect(screen.getByRole('button', { name: 'Preparing rule…' })).toBeDisabled()
  fireEvent.change(screen.getByRole('combobox', { name: 'Brand' }), { target: { value: 'p2' } })
  await screen.findByText('Make it unmistakably Sunday Studio.')
  await act(async () => { finish({ drafted: 1, found: 1 }) })
  expect(screen.queryByText('1 rules ready for your approval.')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'View rule: Protect the logo' })).not.toBeInTheDocument()
  expect(importRules).toHaveBeenCalledWith({ project_id: 'p1', text: 'Keep the logo visible.' })
})


it('accepts a quick instruction immediately without switching input modes', async () => {
  mount(); await openImport()
  const input = screen.getByRole('textbox', { name: 'Quick rule' })
  const submit = screen.getByRole('button', { name: 'Add for approval' })
  expect(submit).toBeDisabled()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Drop your brand guide' })).not.toBeInTheDocument()
  fireEvent.change(input, { target: { value: "  Don’t show that guy with a beard anymore.  " } })
  fireEvent.click(submit)
  await waitFor(() => expect(importRules).toHaveBeenCalledWith({ project_id: 'p1', text: 'Don’t show that guy with a beard anymore.' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(decideSuggestion).not.toHaveBeenCalled()
})


it('keeps PDF import behind a secondary action and preserves an unfinished quick rule', async () => {
  mount(); await openImport()
  fireEvent.change(screen.getByRole('textbox', { name: 'Quick rule' }), { target: { value: 'Keep the logo visible.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Import guidelines' }))
  expect(screen.getByRole('dialog')).toHaveTextContent('PDF')
  fireEvent.click(screen.getByRole('button', { name: 'Close guidelines' }))
  expect(screen.getByRole('textbox', { name: 'Quick rule' })).toHaveValue('Keep the logo visible.')
})


it('shows a brand-specific QA example without the removed helper copy', async () => {
  mount(); await openImport()
  expect(screen.getByRole('textbox', { name: 'Quick rule' })).toHaveAttribute('placeholder', 'Always show the Northline logo on the end card.')
  expect(screen.queryByText(/Write it how you’d say it/)).not.toBeInTheDocument()
  fireEvent.change(screen.getByRole('combobox', { name: 'Brand' }), { target: { value: 'p2' } })
  expect(await screen.findByPlaceholderText('Always show the Sunday Studio logo on the end card.')).toBeInTheDocument()
})


it('accepts Word guidelines through the same document intake as request briefs', async () => {
  render(<SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}><ToastProvider><RulesPage /></ToastProvider></SWRConfig>)
  await screen.findByText('Import guidelines')
  fireEvent.click(screen.getByRole('button', { name: 'Import guidelines' }))
  fireEvent.change(document.querySelector('input[type=file]')!, { target: { files: [new File(['word'], 'guide.docx')] } })
  await waitFor(() => expect(importRules).toHaveBeenCalledWith({ project_id: 'p1', docx_base64: 'd29yZA==' }))
})
