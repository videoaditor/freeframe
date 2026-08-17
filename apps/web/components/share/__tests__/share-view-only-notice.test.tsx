import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { FolderShareViewer } from '../folder-share-viewer'

// A view-only share link renders no comment composer, but the comment panel's empty
// state still read "Leave a comment below to start the review", instructing people to
// use a box that was not there. Reviewers reported it as a broken UI rather than as a
// permission, and a client would more likely have said nothing at all.
describe('folder share - a view-only link says so', () => {
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

  async function openAsset(permission: 'view' | 'comment') {
    render(
      <FolderShareViewer
        token="t" folderName="F" title="T" description={null}
        permission={permission} allowDownload={false} showVersions={false}
        appearance={{ open_in_viewer: true } as never} branding={null}
      />,
    )
    await waitFor(() => expect(screen.getByText('Clip.mp4')).toBeInTheDocument())
    fireEvent.doubleClick(screen.getByText('Clip.mp4'))
    await waitFor(() => expect(screen.getByText('Fields')).toBeInTheDocument(), { timeout: 3000 })
  }

  it('explains the missing composer instead of pointing at it', async () => {
    await openAsset('view')

    await waitFor(
      () => expect(screen.getByText(/View-only access\. Comments are disabled\./)).toBeInTheDocument(),
      { timeout: 3000 },
    )
    expect(screen.queryByText(/Leave a comment below to start the review/)).not.toBeInTheDocument()
  })

  it('stays out of the way when the link does allow comments', async () => {
    await openAsset('comment')

    await waitFor(() => expect(screen.getByText(/No comments yet/)).toBeInTheDocument(), { timeout: 3000 })
    expect(screen.queryByText(/View-only access\. Comments are disabled\./)).not.toBeInTheDocument()
  })
})
