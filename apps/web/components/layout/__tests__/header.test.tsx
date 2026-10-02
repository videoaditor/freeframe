import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { Header } from '../header'
import { useBrandingStore } from '@/stores/branding-store'
import { useBreadcrumbStore } from '@/stores/breadcrumb-store'

const route = vi.hoisted(() => ({ pathname: '/home' }))
vi.mock('next/navigation', () => ({ usePathname: () => route.pathname }))
afterEach(cleanup)
beforeEach(() => {
  useBrandingStore.getState().resetAll()
  useBreadcrumbStore.setState({ labels: {}, extraCrumbs: [] })
})

it.each(['/home', '/rules', '/insights', '/projects'])('shows app identity instead of repeating the root page name on %s', pathname => {
  route.pathname = pathname
  render(<Header onSearchOpen={() => {}} />)
  expect(screen.getByRole('navigation')).toHaveTextContent('Autoreview')
  expect(screen.getByRole('button', { name: 'Search workspace' })).toBeVisible()
})

it('uses custom branding for the root toolbar', () => {
  route.pathname = '/home'
  useBrandingStore.getState().setOrgName('Studio')
  render(<Header onSearchOpen={() => {}} />)
  expect(screen.getByRole('navigation')).toHaveTextContent('Studio')
})

it('preserves named project breadcrumbs and their parent navigation', () => {
  route.pathname = '/projects/12345678-1234-1234-1234-123456789abc'
  useBreadcrumbStore.getState().setLabel('12345678-1234-1234-1234-123456789abc', 'Summer campaign')
  render(<Header onSearchOpen={() => {}} />)
  const nav = within(screen.getByRole('navigation'))
  expect(nav.getByRole('link', { name: 'Projects' })).toHaveAttribute('href', '/projects')
  expect(nav.getByText('Summer campaign')).toBeVisible()
})

it('preserves a folder breadcrumb attached to a root page', () => {
  route.pathname = '/projects'
  useBreadcrumbStore.getState().setExtraCrumbs([{ label: 'Delivery folder' }])
  render(<Header onSearchOpen={() => {}} />)
  const nav = within(screen.getByRole('navigation'))
  expect(nav.getByRole('link', { name: 'Projects' })).toHaveAttribute('href', '/projects')
  expect(nav.getByText('Delivery folder')).toBeVisible()
})
