import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { FolderShareViewer } from '../folder-share-viewer'

describe('mobile share review comment controls', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200,
      json: async () => ({ assets: [{ id: 'a1', name: 'Clip.mp4', asset_type: 'video', latest_version_id: 'v1', thumbnail_url: null, status: 'ready' }], subfolders: [], total: 1 }),
    })) as unknown as typeof fetch)
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    vi.stubGlobal('matchMedia', (query: string) => ({ matches: false, media: query, onchange: null,
      addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent: () => false,
    }))
  })
  afterEach(() => { vi.unstubAllGlobals() })

  it('lets a mobile reviewer reveal and hide feedback using named controls', async () => {
    render(<FolderShareViewer token="t" folderName="F" title="T" description={null}
      permission="comment" allowDownload={false} showVersions={false}
      appearance={{ open_in_viewer: true } as never} branding={null} />)
    await waitFor(() => expect(screen.getByText('Clip.mp4')).toBeInTheDocument())
    fireEvent.doubleClick(screen.getByText('Clip.mp4'))
    const show = await screen.findByRole('button', { name: 'Show comments' })
    expect(show).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(show)
    await waitFor(() => expect(screen.getByPlaceholderText(/comment/i)).toBeInTheDocument(), { timeout: 3000 })
    const hide = screen.getByRole('button', { name: 'Hide comments' })
    expect(hide).toHaveAttribute('aria-expanded', 'true')
    fireEvent.click(hide)
    await waitFor(() => expect(screen.queryByPlaceholderText(/comment/i)).not.toBeInTheDocument())
  })
})
