import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import LoginPage from '../page'

const m = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), replace: vi.fn(), getAccessToken: vi.fn() }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace: m.replace }) }))
vi.mock('@/lib/api', () => ({ api: { get: m.get, post: m.post }, ApiError: class extends Error { detail = 'Failed' } }))
vi.mock('@/lib/auth', () => ({ getAccessToken: m.getAccessToken, setTokens: vi.fn() }))
vi.mock('@/stores/auth-store', () => ({ useAuthStore: { getState: () => ({ fetchUser: vi.fn(), user: null }) } }))

const assign = vi.fn()

function mockApi({ needsSetup = false, gateEnabled = true }: { needsSetup?: boolean, gateEnabled?: boolean } = {}) {
  m.get.mockImplementation((url: string) => {
    if (url === '/setup/status') return Promise.resolve({ needs_setup: needsSetup })
    if (url === '/auth/oidc/config') return Promise.resolve({ enabled: gateEnabled })
    return Promise.resolve({})
  })
}

function setUrl(path: string) {
  const [pathname, search = ''] = path.split('?')
  vi.stubGlobal('location', { ...window.location, pathname, search: search ? `?${search}` : '', assign })
}

beforeEach(() => {
  m.getAccessToken.mockReturnValue(null)
  mockApi()
  setUrl('/login')
})
afterEach(() => { vi.clearAllMocks(); vi.unstubAllGlobals() })

it('sends an already-authenticated visitor straight to the destination, never painting the form', async () => {
  m.getAccessToken.mockReturnValue('a-token')
  render(<LoginPage />)
  await waitFor(() => expect(m.replace).toHaveBeenCalledWith('/home'))
  expect(assign).not.toHaveBeenCalled()
  expect(screen.queryByRole('button', { name: 'Sign in with Aditor' })).not.toBeInTheDocument()
})

it('honors an authenticated from= param', async () => {
  m.getAccessToken.mockReturnValue('a-token')
  setUrl('/login?from=%2Fhandin')
  render(<LoginPage />)
  await waitFor(() => expect(m.replace).toHaveBeenCalledWith('/handin'))
})

it('redirects to /setup when first-time setup is needed', async () => {
  mockApi({ needsSetup: true })
  render(<LoginPage />)
  await waitFor(() => expect(m.replace).toHaveBeenCalledWith('/setup'))
  expect(assign).not.toHaveBeenCalled()
})

it('bounces a cold signed-out visit straight to the gate', async () => {
  mockApi({ gateEnabled: true })
  render(<LoginPage />)
  await waitFor(() => expect(assign).toHaveBeenCalledTimes(1))
  expect(assign.mock.calls[0][0]).toContain('/auth/oidc/login')
})

it('does not auto-bounce when the URL carries a gate error, and shows it instead', async () => {
  setUrl('/login?error=gate_sign_in_expired')
  render(<LoginPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent('expired')
  expect(assign).not.toHaveBeenCalled()
})

it('falls back to the login form when the gate is not configured', async () => {
  mockApi({ gateEnabled: false })
  render(<LoginPage />)
  expect(await screen.findByLabelText('Email address')).toBeVisible()
  expect(assign).not.toHaveBeenCalled()
})
