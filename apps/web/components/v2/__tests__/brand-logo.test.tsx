import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SWRConfig } from 'swr'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { BrandLogo } from '../brand-logo'
import { getBrandLogo, uploadBrandLogo } from '@/lib/platform'

vi.mock('@/lib/platform', () => ({ getBrandLogo: vi.fn(), uploadBrandLogo: vi.fn() }))
afterEach(cleanup)
beforeEach(() => { vi.resetAllMocks(); vi.mocked(getBrandLogo).mockResolvedValue('https://example.test/old.webp') })
function mount(projectId = 'brand-a') {
  return render(<SWRConfig value={{ provider: () => new Map(), shouldRetryOnError: false }}><BrandLogo projectId={projectId} brandName="Northline" /></SWRConfig>)
}
const pick = () => fireEvent.change(screen.getByLabelText('Choose brand logo'), { target: { files: [new File(['image'], 'logo.png', { type: 'image/png' })] } })

it('saves to the selected project and only replaces the preview after success', async () => {
  let finish!: (url: string) => void
  vi.mocked(uploadBrandLogo).mockImplementation(() => new Promise(resolve => { finish = resolve }))
  mount()
  await screen.findByRole('button', { name: 'Change logo' })
  pick()
  expect(screen.getByRole('button', { name: 'Saving logo…' })).toBeDisabled()
  expect(screen.getByRole('img')).toHaveAttribute('src', 'https://example.test/old.webp')
  expect(uploadBrandLogo).toHaveBeenCalledWith('brand-a', expect.any(File))
  finish('https://example.test/new.webp')
  await waitFor(() => expect(screen.getByRole('img')).toHaveAttribute('src', 'https://example.test/new.webp'))
  expect(screen.getByRole('status')).toHaveTextContent('Logo saved')
})

it('retains the previous logo on failure and allows retry with the same file', async () => {
  vi.mocked(uploadBrandLogo).mockRejectedValueOnce(new Error('Upload failed')).mockResolvedValueOnce('https://example.test/new.webp')
  mount()
  await screen.findByRole('button', { name: 'Change logo' })
  pick()
  expect(await screen.findByRole('alert')).toHaveTextContent('Upload failed')
  expect(screen.getByRole('img')).toHaveAttribute('src', 'https://example.test/old.webp')
  pick()
  await waitFor(() => expect(screen.getByRole('img')).toHaveAttribute('src', 'https://example.test/new.webp'))
})

it('shows a retry on read failure instead of pretending no logo exists', async () => {
  vi.mocked(getBrandLogo).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(null)
  mount()
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not load')
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
  await screen.findByRole('button', { name: 'Upload logo' })
})

it('rejects oversized files before uploading', async () => {
  mount()
  await screen.findByRole('button', { name: 'Change logo' })
  const file = new File(['image'], 'large.png', { type: 'image/png' })
  Object.defineProperty(file, 'size', { value: 6 * 1024 * 1024 })
  fireEvent.change(screen.getByLabelText('Choose brand logo'), { target: { files: [file] } })
  expect(screen.getByRole('alert')).toHaveTextContent('5 MB')
  expect(uploadBrandLogo).not.toHaveBeenCalled()
})

it('keeps a late upload for the previous brand out of the newly selected brand', async () => {
  vi.mocked(getBrandLogo).mockImplementation(async id => id === 'brand-a' ? 'https://example.test/a.webp' : null)
  let finish!: (url: string) => void
  vi.mocked(uploadBrandLogo).mockImplementation(() => new Promise(resolve => { finish = resolve }))
  const cache = new Map()
  const view = (id: string) => <SWRConfig value={{ provider: () => cache, shouldRetryOnError: false }}><BrandLogo projectId={id} brandName={id} /></SWRConfig>
  const { rerender } = render(view('brand-a'))
  await screen.findByRole('button', { name: 'Change logo' })
  pick()
  rerender(view('brand-b'))
  await screen.findByRole('button', { name: 'Upload logo' })
  await act(async () => { finish('https://example.test/a-new.webp') })
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Upload logo' })).toBeEnabled()
})
