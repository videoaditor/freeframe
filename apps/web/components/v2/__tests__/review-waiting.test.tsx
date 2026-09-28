import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { UploadCard } from '../upload-card'

afterEach(cleanup)
it('uses measured upload progress but never presents review as 100 percent complete', () => {
  const { rerender } = render(<UploadCard name="Launch.mp4" size={100} progress={.73} phase="uploading" />)
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '73')
  rerender(<UploadCard name="Launch.mp4" size={100} progress={1} phase="reviewing" />)
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  expect(screen.queryByText('100%')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Pause waiting animation' }))
  expect(screen.getByRole('button', { name: 'Play waiting animation' })).toBeInTheDocument()
})
