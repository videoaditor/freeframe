import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SWRConfig } from 'swr'
import { afterEach, expect, it, vi } from 'vitest'
import HandinPage from '@/app/(dashboard)/handin/page'
vi.mock('@/lib/iterations', () => ({ partsEnabled: true }))
vi.mock('../parts-handin', () => ({ PartsHandin: () => <p>Part uploader</p> }))
vi.mock('@/hooks/use-page-title', () => ({ usePageTitle: vi.fn() }))
vi.mock('@/lib/handin', () => ({ GATE_BASE: '', isHandinConfigured: () => true, lookUpCard: vi.fn().mockResolvedValue({ name: 'Launch' }) }))
vi.mock('@/lib/api', () => ({ api: { get: vi.fn().mockImplementation((path: string) => Promise.resolve(path === '/projects' ? [{ id: 'p', name: 'Brand', is_workspace: true }] : [])), post: vi.fn().mockResolvedValue({ id: 'folder' }) } }))
vi.mock('../workspace-picker', () => ({ WorkspacePicker: ({ onChange }: { onChange: (x: unknown) => void }) => <button type="button" onClick={() => onChange({ kind: 'existing', id: 'p', name: 'Brand' })}>Pick workspace</button> }))
vi.mock('@/components/upload/upload-zone', () => ({ UploadZone: ({ onFilesSelected }: { onFilesSelected: (f: File[]) => void }) => <button type="button" onClick={() => onFilesSelected([new File(['v'], 'cut.mp4')])}>Pick video</button> }))
vi.mock('@/stores/upload-store', () => { const state = { files: [], startUpload: () => 'pending' }; return { useUploadStore: Object.assign((select: (s: typeof state) => unknown) => select(state), { getState: () => state, subscribe: () => () => {} }) } })
afterEach(cleanup)
it('locks submission format when the complete-ad workflow starts', async () => {
  render(<SWRConfig value={{ provider: () => new Map() }}><HandinPage /></SWRConfig>)
  fireEvent.click(screen.getByRole('button', { name: 'Complete ads' }))
  fireEvent.click(screen.getByRole('button', { name: 'Pick workspace' }))
  fireEvent.click(screen.getByRole('button', { name: 'Pick video' }))
  fireEvent.change(screen.getByLabelText('Trello card link'), { target: { value: 'https://trello.com/c/preview' } })
  fireEvent.click(screen.getByRole('button', { name: 'Hand in' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Separate parts' })).toBeDisabled())
  expect(screen.getByRole('button', { name: 'Complete ads' })).toBeDisabled()
})
