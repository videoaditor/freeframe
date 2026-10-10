import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SWRConfig } from 'swr'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { RequestSheet } from '../request-sheet'
import { api } from '@/lib/api'
import { createRequest } from '@/lib/platform'

vi.mock('@/lib/api', () => ({ api: { get: vi.fn() } }))
vi.mock('@/lib/platform', async importOriginal => ({ ...await importOriginal<typeof import('@/lib/platform')>(), createRequest: vi.fn() }))
vi.mock('../brand-logo', () => ({ BrandLogo: () => null }))
vi.mock('../link-card', () => ({ LinkCard: () => <p>Link ready</p> }))
vi.mock('@/stores/auth-store', () => ({ useAuthStore: (selector: (s: unknown) => unknown) => selector({ user: { is_staff: false } }) }))
afterEach(cleanup)
it('starts a request in the brand whose project the owner opened', async () => {
  vi.mocked(api.get).mockResolvedValue([{ id: 'brand1', name: 'Northline' }, { id: 'brand2', name: 'Sunday Studio' }])
  render(<SWRConfig value={{ provider: () => new Map() }}><RequestSheet open initialProjectId="brand2" onOpenChange={vi.fn()} /></SWRConfig>)
  await waitFor(() => expect(screen.getByRole('combobox', { name: 'Brand' })).toHaveTextContent('Sunday Studio'))
  fireEvent.change(screen.getByRole('textbox', { name: 'Title' }), { target: { value: 'New delivery' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create link' }))
  await waitFor(() => expect(createRequest).toHaveBeenCalledWith(expect.objectContaining({ project_id: 'brand2' })))
})
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(api.get).mockResolvedValue([{ id: 'brand1', name: 'Northline' }])
  vi.mocked(createRequest).mockRejectedValue(new Error('Please retry.'))
})
async function mount() {
  const view = render(<SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}><RequestSheet open onOpenChange={vi.fn()} /></SWRConfig>)
  await screen.findByText('Northline')
  fireEvent.change(screen.getByRole('textbox', { name: 'Title' }), { target: { value: 'Launch' } })
  return view
}
it('exposes links beside files and keeps a failed request intact for retry', async () => {
  await mount()
  expect(screen.getByRole('button', { name: 'Drop a briefing' })).toBeInTheDocument()
  fireEvent.change(screen.getByRole('textbox', { name: 'Briefing text or link' }), { target: { value: 'https://docs.google.com/document/d/test' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create link' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Please retry')
  expect(createRequest).toHaveBeenCalledWith({ project_id: 'brand1', title: 'Launch', brief_text: '', brief_url: 'https://docs.google.com/document/d/test', brief_pdf_base64: '', idempotency_key: expect.any(String) })
  expect(screen.getByRole('textbox', { name: 'Title' })).toHaveValue('Launch')
})
it('sends Markdown contents through brief_text, along with an optional link', async () => {
  const view = await mount()
  const file = new File(['# Launch\nKeep the logo visible.'], 'brief.md', { type: 'text/markdown' })
  fireEvent.change(view.container.ownerDocument.querySelector('input[type=file]')!, { target: { files: [file] } })
  fireEvent.change(screen.getByRole('textbox', { name: 'Briefing text or link' }), { target: { value: 'https://example.test/brief' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create link' }))
  await waitFor(() => expect(createRequest).toHaveBeenCalledWith({ project_id: 'brand1', title: 'Launch', brief_text: '# Launch\nKeep the logo visible.', brief_url: 'https://example.test/brief', brief_pdf_base64: '', idempotency_key: expect.any(String) }))
})
it('does not send unsupported files to the server', async () => {
  const view = await mount()
  fireEvent.change(view.container.ownerDocument.querySelector('input[type=file]')!, { target: { files: [new File(['x'], 'brief.exe')] } })
  fireEvent.click(screen.getByRole('button', { name: 'Create link' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('PDF, Markdown')
  expect(createRequest).not.toHaveBeenCalled()
})
it('reuses the create identity after a lost response and changes it for a new brief', async () => {
  await mount()
  fireEvent.click(screen.getByRole('button', { name: 'Create link' }))
  await screen.findByRole('alert')
  const first=vi.mocked(createRequest).mock.calls[0][0].idempotency_key
  expect(first).toEqual(expect.any(String))
  fireEvent.click(screen.getByRole('button', { name: 'Create link' }))
  await waitFor(()=>expect(createRequest).toHaveBeenCalledTimes(2))
  expect(vi.mocked(createRequest).mock.calls[1][0].idempotency_key).toBe(first)
  await waitFor(()=>expect(screen.getByRole('button',{name:'Create link'})).not.toBeDisabled())
  fireEvent.change(screen.getByRole('textbox',{name:'Briefing text or link'}),{target:{value:'New briefing'}})
  fireEvent.click(screen.getByRole('button',{name:'Create link'}))
  await waitFor(()=>expect(createRequest).toHaveBeenCalledTimes(3))
  expect(vi.mocked(createRequest).mock.calls[2][0].idempotency_key).not.toBe(first)
})

it('starts a new assignment when the sheet is reopened with the same brief', async () => {
  const view = await mount()
  fireEvent.click(screen.getByRole('button', { name: 'Create link' }))
  await screen.findByRole('alert')
  const first=vi.mocked(createRequest).mock.calls[0][0].idempotency_key
  const config={provider:()=>new Map(),dedupingInterval:0}
  view.rerender(<SWRConfig value={config}><RequestSheet open={false} onOpenChange={vi.fn()} /></SWRConfig>)
  view.rerender(<SWRConfig value={config}><RequestSheet open onOpenChange={vi.fn()} /></SWRConfig>)
  fireEvent.change(screen.getByRole('textbox', {name:'Title'}), {target:{value:'Launch'}})
  fireEvent.click(screen.getByRole('button', {name:'Create link'}))
  await waitFor(()=>expect(createRequest).toHaveBeenCalledTimes(2))
  expect(vi.mocked(createRequest).mock.calls[1][0].idempotency_key).not.toBe(first)
})


it('shows the only brand as context without asking the owner to choose it', async () => {
  await mount()
  expect(screen.queryByRole('combobox', { name: 'Brand' })).not.toBeInTheDocument()
  expect(screen.getByText('Northline').parentElement).toHaveTextContent('For Northline')
})

it('passes a Word brief to the server for document parsing', async () => {
  const view = await mount()
  fireEvent.change(view.container.ownerDocument.querySelector('input[type=file]')!, { target: { files: [new File(['docx'], 'brief.docx')] } })
  fireEvent.click(screen.getByRole('button', { name: 'Create link' }))
  await waitFor(() => expect(createRequest).toHaveBeenCalledWith(expect.objectContaining({ brief_docx_base64: 'ZG9jeA==' })))
})


it('uses the remaining brand when the previously selected brand is no longer available', async () => {
  vi.mocked(api.get).mockResolvedValue([{ id: 'brand1', name: 'Northline' }, { id: 'brand2', name: 'Sunday Studio' }])
  const cache = new Map()
  const config = { provider: () => cache, dedupingInterval: 0 }
  const view = render(<SWRConfig value={config}><RequestSheet open initialProjectId="brand2" onOpenChange={vi.fn()} /></SWRConfig>)
  await waitFor(() => expect(screen.getByRole('combobox', { name: 'Brand' })).toHaveTextContent('Sunday Studio'))
  view.rerender(<SWRConfig value={config}><RequestSheet open={false} initialProjectId="brand2" onOpenChange={vi.fn()} /></SWRConfig>)
  vi.mocked(api.get).mockResolvedValue([{ id: 'brand1', name: 'Northline' }])
  view.rerender(<SWRConfig value={config}><RequestSheet open initialProjectId="brand2" onOpenChange={vi.fn()} /></SWRConfig>)
  await waitFor(() => expect(screen.queryByRole('combobox', { name: 'Brand' })).not.toBeInTheDocument())
  expect(screen.getByText('Northline').parentElement).toHaveTextContent('For Northline')
  fireEvent.change(screen.getByRole('textbox', { name: 'Title' }), { target: { value: 'Launch' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create link' }))
  await waitFor(() => expect(createRequest).toHaveBeenCalledWith(expect.objectContaining({ project_id: 'brand1' })))
})
