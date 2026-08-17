import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { FolderShareViewer } from '../folder-share-viewer'

// The share viewer reuses the internal composer, so a client was offered the
// Public/Internal selector. The guest endpoint has no `visibility` field, so
// picking Internal posted a public comment anyway: it told a client that a
// team-only channel exists and then showed them a choice that was discarded.
describe('folder share - no internal-comment control for guests', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        assets: [{ id: 'a1', name: 'Clip.mp4', asset_type: 'video', latest_version_id: 'v1', thumbnail_url: null, status: 'ready' }],
        subfolders: [],
        total: 1,
      }),
    })) as unknown as typeof fetch)
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    // jsdom has no matchMedia (#188); the panel default reads it during render.
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches: true, media: query, onchange: null,
      addEventListener() {}, removeEventListener() {},
      addListener() {}, removeListener() {}, dispatchEvent: () => false,
    }))
  })

  afterEach(() => { vi.unstubAllGlobals() })

  it('offers no visibility selector on a link that does allow comments', async () => {
    render(
      <FolderShareViewer
        token="t" folderName="F" title="T" description={null}
        permission="comment" allowDownload={false} showVersions={false}
        appearance={{ open_in_viewer: true } as never} branding={null}
      />,
    )

    await waitFor(() => expect(screen.getByText('Clip.mp4')).toBeInTheDocument())
    fireEvent.doubleClick(screen.getByText('Clip.mp4'))

    // Wait for the composer itself, so absence below is a real absence and not
    // an assertion that ran before the dynamic import resolved.
    await waitFor(
      () => expect(screen.getByPlaceholderText(/comment/i)).toBeInTheDocument(),
      { timeout: 3000 },
    )

    expect(screen.queryByText('Internal')).not.toBeInTheDocument()
    expect(screen.queryByText('Public')).not.toBeInTheDocument()
  })
})
