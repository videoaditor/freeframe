import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { BriefInput } from '../brief-input'
import { useBriefTitle } from '@/hooks/use-brief-title'
function Harness() {
  const [file, setFile] = useState<File | null>(null), [text, setText] = useState(''), [title, setTitle] = useState('')
  const automatic = useBriefTitle(file, text, setTitle)
  return <><input aria-label="Title" value={title} onChange={e => { automatic.edit(); setTitle(e.target.value) }} /><BriefInput file={file} onFile={setFile} text={text} onText={setText} /></>
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
it('hides text by default, pastes a link inside the drop field, and suggests a readable title', async () => {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { readText: vi.fn().mockResolvedValue('https://example.com/Summer-launch-brief') } })
  const view = render(<Harness />)
  expect(screen.queryByRole('textbox', { name: 'Briefing text or link' })).not.toBeInTheDocument()
  expect(view.container.querySelector('button button')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Paste link' }))
  await waitFor(() => expect(screen.getByRole('textbox', { name: 'Briefing link' })).toHaveValue('https://example.com/Summer-launch-brief'))
  expect(screen.getByRole('textbox', { name: 'Title' })).toHaveValue('Summer launch brief')
})
it('shows a usable manual link input when clipboard permission is denied', async () => {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { readText: vi.fn().mockRejectedValue(new Error('Denied')) } })
  render(<Harness />)
  fireEvent.click(screen.getByRole('button', { name: 'Paste link' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Paste your document link below.')
  fireEvent.change(screen.getByRole('textbox', { name: 'Briefing link' }), { target: { value: 'https://example.com/new-brief' } })
  expect(screen.getByRole('textbox', { name: 'Title' })).toHaveValue('new brief')
})
it('suggests a file title but preserves manual naming when another file is selected', async () => {
  const view = render(<Harness />)
  const input = view.container.querySelector('input[type=file]')!
  fireEvent.change(input, { target: { files: [new File(['pdf'], 'Summer_launch.pdf', { type: 'application/pdf' })] } })
  expect(screen.getByRole('textbox', { name: 'Title' })).toHaveValue('Summer launch')
  fireEvent.change(screen.getByRole('textbox', { name: 'Title' }), { target: { value: 'My campaign' } })
  fireEvent.click(screen.getByRole('button', { name: 'Remove Summer_launch.pdf' }))
  fireEvent.change(view.container.querySelector('input[type=file]')!, { target: { files: [new File(['# Different heading'], 'other.md')] } })
  await waitFor(() => expect(screen.getByText('other.md')).toBeInTheDocument())
  expect(screen.getByRole('textbox', { name: 'Title' })).toHaveValue('My campaign')
})
it('retains pasted text when its compact alternative is collapsed', () => {
  render(<Harness />)
  fireEvent.click(screen.getByRole('button', { name: 'Paste text instead' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Briefing text or link' }), { target: { value: 'Show our product.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Hide text' }))
  fireEvent.click(screen.getByRole('button', { name: 'Paste text instead' }))
  expect(screen.getByRole('textbox', { name: 'Briefing text or link' })).toHaveValue('Show our product.')
})
it('does not apply URL validation to text after switching modes and collapsing it', async () => {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { readText: vi.fn().mockRejectedValue(new Error('Denied')) } })
  render(<Harness />)
  fireEvent.click(screen.getByRole('button', { name: 'Paste link' }))
  await screen.findByRole('status')
  fireEvent.click(screen.getByRole('button', { name: 'Paste text instead' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Briefing text or link' }), { target: { value: 'Show our product.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Hide text' }))
  expect(screen.queryByRole('textbox', { name: 'Briefing link' })).not.toBeInTheDocument()
})
it('does not overwrite a manual name when a document title arrives later', async () => {
  let resolve!: (r: Response) => void
  const fetcher = vi.fn(() => new Promise<Response>(r => { resolve = r })); vi.stubGlobal('fetch', fetcher)
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { readText: vi.fn().mockResolvedValue('https://docs.google.com/document/d/1234567890/edit') } })
  render(<Harness />)
  fireEvent.click(screen.getByRole('button', { name: 'Paste link' }))
  await waitFor(() => expect(fetcher).toHaveBeenCalled())
  fireEvent.change(screen.getByRole('textbox', { name: 'Title' }), { target: { value: 'My launch' } })
  await act(async () => { resolve(new Response(JSON.stringify({ title: 'Document title' }))); await Promise.resolve() })
  await waitFor(() => expect(screen.getByRole('textbox', { name: 'Title' })).toHaveValue('My launch'))
})
