import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AssetGrid } from '../asset-grid'
import type { Asset } from '@/types'

function makeAsset(id: string): Asset {
  return {
    id,
    project_id: 'p1',
    name: `Asset ${id}`,
    description: null,
    asset_type: 'video',
    status: 'draft',
    rating: null,
    assignee_id: null,
    folder_id: null,
    due_date: null,
    keywords: [],
    created_by: 'u1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    deleted_at: null,
  }
}

const assets = [makeAsset('a'), makeAsset('b'), makeAsset('c')]

// Follow-up to 843c163e8: clicking anywhere on the card should drive
// selection, not just the tiny checkbox, while opening stays on double-click
// (or the dedicated title-click affordance).
describe('AssetGrid card-wide selection (Frame.io-style)', () => {
  it('plain click on the card selects only that asset, replacing prior selection', () => {
    const onAssetSelect = vi.fn()
    const onAssetOpen = vi.fn()
    render(
      <AssetGrid
        assets={assets}
        projectId="p1"
        onAssetSelect={onAssetSelect}
        onAssetOpen={onAssetOpen}
      />,
    )

    fireEvent.click(screen.getByTestId('asset-card-a'))
    fireEvent.click(screen.getByTestId('asset-card-b'))

    // Selecting b should replace a — the bottom bar reflects a single selection.
    expect(screen.getByText('1 Item selected')).toBeInTheDocument()
    expect(onAssetSelect).toHaveBeenCalled()
    expect(onAssetOpen).not.toHaveBeenCalled()
  })

  it('cmd/ctrl-click toggles the asset into the multi-selection without clearing it', () => {
    render(<AssetGrid assets={assets} projectId="p1" />)

    fireEvent.click(screen.getByTestId('asset-card-a'), { metaKey: true })
    fireEvent.click(screen.getByTestId('asset-card-b'), { ctrlKey: true })

    expect(screen.getByText('2 Items selected')).toBeInTheDocument()

    // ctrl-clicking b again toggles it back out.
    fireEvent.click(screen.getByTestId('asset-card-b'), { ctrlKey: true })
    expect(screen.getByText('1 Item selected')).toBeInTheDocument()
  })

  it('shift-click extends the range from the last click', () => {
    render(<AssetGrid assets={assets} projectId="p1" />)

    fireEvent.click(screen.getByTestId('asset-card-a'))
    fireEvent.click(screen.getByTestId('asset-card-c'), { shiftKey: true })

    expect(screen.getByText('3 Items selected')).toBeInTheDocument()
  })

  it('double-click on the card opens the asset; single click never navigates', () => {
    const onAssetOpen = vi.fn()
    render(<AssetGrid assets={assets} projectId="p1" onAssetOpen={onAssetOpen} />)

    fireEvent.click(screen.getByTestId('asset-card-a'))
    expect(onAssetOpen).not.toHaveBeenCalled()

    fireEvent.doubleClick(screen.getByTestId('asset-card-a'))
    expect(onAssetOpen).toHaveBeenCalledWith(assets[0])
  })

  it('clicking the title text opens the asset without changing selection', () => {
    const onAssetOpen = vi.fn()
    const onAssetSelect = vi.fn()
    render(<AssetGrid assets={assets} projectId="p1" onAssetOpen={onAssetOpen} onAssetSelect={onAssetSelect} />)

    fireEvent.click(screen.getByText('Asset a'))

    expect(onAssetOpen).toHaveBeenCalledWith(assets[0])
    expect(onAssetSelect).not.toHaveBeenCalled()
  })

  it('clicking the checkbox still toggles single selection without replacing others', () => {
    render(<AssetGrid assets={assets} projectId="p1" />)

    fireEvent.click(screen.getAllByLabelText('Select asset')[0])
    fireEvent.click(screen.getAllByLabelText('Select asset')[1])

    expect(screen.getByText('2 Items selected')).toBeInTheDocument()
  })
})
