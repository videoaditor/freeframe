import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SWRConfig } from 'swr'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { PartsWorkspace } from '../parts-workspace'
import { declareParts, requestIterations, submitParts, type IterationProgress } from '@/lib/iterations'
import { uploadToRequest } from '@/lib/platform'
vi.mock('@/lib/iterations', async original => ({ ...await original<typeof import('@/lib/iterations')>(), declareParts: vi.fn(), requestIterations: vi.fn(), submitParts: vi.fn() }))
vi.mock('@/lib/platform', async original => ({ ...await original<typeof import('@/lib/platform')>(), uploadToRequest: vi.fn() }))
vi.mock('../request-workspace', () => ({ RequestWorkspace: () => <div>Part feedback</div> }))
const base: IterationProgress = { enabled: true, mode: 'components', simple: true, manifest: { schema_version: 1, summary: '', slots: [], recipes: [] }, slots: [], outputs: [], state: 'waiting', delivered: 0, total: 0, submitted: false, can_leave: false, editor_done: false }
beforeEach(() => { vi.resetAllMocks(); vi.mocked(requestIterations).mockResolvedValue(base); vi.mocked(declareParts).mockResolvedValue(base) })
afterEach(cleanup)
const mount = () => render(<SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}><PartsWorkspace token="test" who={{ name: 'Fred', email: 'fred@example.test' }} /></SWRConfig>)
it('declares roles before starting upload on drop; does not submit the batch automatically', async () => {
  vi.mocked(uploadToRequest).mockResolvedValue({ asset_id: 'h1', version_number: 1 })
  const view = mount()
  const zone = await screen.findByLabelText('Upload hooks')
  fireEvent.change(zone, { target: { files: [new File(['a'], 'hook.mp4', { type: 'video/mp4' })] } })
  await waitFor(() => expect(uploadToRequest).toHaveBeenCalled())
  expect(declareParts).toHaveBeenCalledWith('test', [expect.objectContaining({ role: 'hook', label: 'hook.mp4' })])
  expect(vi.mocked(declareParts).mock.invocationCallOrder[0]).toBeLessThan(vi.mocked(uploadToRequest).mock.invocationCallOrder[0])
  expect(uploadToRequest).toHaveBeenCalledWith('test', expect.objectContaining({ name: 'Fred' }), expect.any(File), expect.any(Function), expect.objectContaining({ slotId: expect.any(String) }))
  expect(submitParts).not.toHaveBeenCalled()
  view.unmount()
})
it('keeps the browser-open message and submit disabled during transfers even if server previously allowed leaving', async () => {
  vi.mocked(uploadToRequest).mockReturnValue(new Promise(() => {}))
  mount()
  fireEvent.change(await screen.findByLabelText('Upload bodies'), { target: { files: [new File(['b'], 'body.mp4', { type: 'video/mp4' })] } })
  expect(await screen.findByText('Keep this tab open until all files are saved.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Submit for review' })).toBeDisabled()
})
it('restores truthful background handoff state when reopening a submitted link', async () => {
  vi.mocked(requestIterations).mockResolvedValue({ ...base, submitted: true, can_leave: true, editor_done: true, state: 'rendering', total: 8, delivered: 6 })
  mount()
  expect(await screen.findByText('Your part is done')).toBeInTheDocument()
  expect(screen.queryByText('8 ads delivered')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Submit for review' })).not.toBeInTheDocument()
})
it('accepts signed-in identity that arrives after mount, including an in-flight upload', async () => {
  const provider = new Map()
  vi.mocked(uploadToRequest).mockImplementation(async (_token, _who, _file, _progress, options) => {
    const identity = await options!.identity!()
    expect(identity.email).toBe('fred@example.test')
    return { asset_id: 'h1', version_number: 1 }
  })
  const view = render(<SWRConfig value={{ provider: () => provider }}><PartsWorkspace token="test" /></SWRConfig>)
  fireEvent.change(await screen.findByLabelText('Upload hooks'), { target: { files: [new File(['a'], 'hook.mp4', { type: 'video/mp4' })] } })
  await waitFor(() => expect(uploadToRequest).toHaveBeenCalled())
  view.rerender(<SWRConfig value={{ provider: () => provider }}><PartsWorkspace token="test" who={{ name: 'Fred', email: 'fred@example.test' }} /></SWRConfig>)
  await waitFor(() => expect(screen.queryByText('Keep this tab open until all files are saved.')).not.toBeInTheDocument())
})
const saved: IterationProgress = { ...base, total: 1, manifest: { ...base.manifest, slots: [{ id: 'h', label: 'Hook.mp4', role: 'hook', group: '', script: '' }, { id: 'b', label: 'Body.mp4', role: 'body', group: '', script: '' }] }, slots: [{ slot_id: 'h', asset_id: 'ha', version_id: 'hv', version_number: 1, status: 'clear', findings: [], bytes_stored: true }, { slot_id: 'b', asset_id: 'ba', version_id: 'bv', version_number: 1, status: 'reviewing', findings: [], bytes_stored: true }] }
it('seals the complete saved batch explicitly and displays only the returned server handoff', async () => {
  vi.mocked(requestIterations).mockResolvedValue(saved)
  vi.mocked(submitParts).mockResolvedValue({ ...saved, submitted: true, can_leave: true, editor_done: false })
  mount()
  fireEvent.click(await screen.findByRole('button', { name: 'Submit for review' }))
  await waitFor(() => expect(submitParts).toHaveBeenCalledWith('test'))
  expect(await screen.findByText('Submitted · checking your parts')).toBeInTheDocument()
  expect(screen.queryByText('Your part is done')).not.toBeInTheDocument()
})
it('does not seal after reload when a bound version still has unsaved bytes', async () => {
  vi.mocked(requestIterations).mockResolvedValue({ ...saved, slots: saved.slots.map(s => ({ ...s, bytes_stored: false })) })
  mount()
  expect(await screen.findByRole('button', { name: 'Submit for review' })).toBeDisabled()
})
it('replaces the selected part using its exact asset binding instead of declaring another part', async () => {
  vi.mocked(requestIterations).mockResolvedValue({ ...saved, submitted: true, state: 'held' })
  vi.mocked(uploadToRequest).mockReturnValue(new Promise(() => {}))
  mount()
  fireEvent.change(await screen.findByLabelText('Replace Hook.mp4'), { target: { files: [new File(['v2'], 'Different filename.mp4', { type: 'video/mp4' })] } })
  await waitFor(() => expect(uploadToRequest).toHaveBeenCalledWith('test', expect.any(Object), expect.any(File), expect.any(Function), expect.objectContaining({ slotId: 'h', assetId: 'ha' })))
  expect(declareParts).not.toHaveBeenCalled()
  expect(screen.queryByText('Your part is done')).not.toBeInTheDocument()
})
