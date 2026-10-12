import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

const m = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), replace: vi.fn(), getAccessToken: vi.fn() }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace: m.replace }) }))
vi.mock('@/lib/api', () => ({ api: { get: m.get, post: m.post }, ApiError: class extends Error { detail = 'Failed' } }))
vi.mock('@/lib/auth', () => ({ getAccessToken: m.getAccessToken, setTokens: vi.fn() }))
vi.mock('@/stores/auth-store', () => ({ useAuthStore: { getState: () => ({ fetchUser: vi.fn(), user: null }) } }))

const assign = vi.fn()

function mockApi({ needsSetup = false }: { needsSetup?: boolean } = {}) {
  m.get.mockImplementation((url: string) => {
    if (url === '/setup/status') return Promise.resolve({ needs_setup: needsSetup })
    return Promise.resolve({})
  })
}

function setUrl(path: string) {
  const [pathname, search = ''] = path.split('?')
  vi.stubGlobal('location', { ...window.location, pathname, search: search ? `?${search}` : '', assign })
}

// OIDC_ENABLED is read from the baked NEXT_PUBLIC_OIDC_ENABLED at module load, so
// set it before importing the page and re-import per test (as the middleware test does).
async function loadPage(oidcEnabled: boolean) {
  vi.resetModules()
  process.env.NEXT_PUBLIC_OIDC_ENABLED = oidcEnabled ? 'true' : 'false'
  return (await import('../page')).default
}

beforeEach(() => {
  m.getAccessToken.mockReturnValue(null)
  mockApi()
  setUrl('/login')
})
afterEach(() => { vi.clearAllMocks(); vi.unstubAllGlobals(); delete process.env.NEXT_PUBLIC_OIDC_ENABLED })

it('sends an already-authenticated visitor straight to the destination, never painting the form', async () => {
  const LoginPage = await loadPage(true)
  m.getAccessToken.mockReturnValue('a-token')
  render(<LoginPage />)
  await waitFor(() => expect(m.replace).toHaveBeenCalledWith('/home'))
  expect(assign).not.toHaveBeenCalled()
  expect(screen.queryByRole('button', { name: 'Sign in with Aditor' })).not.toBeInTheDocument()
})

it('honors an authenticated from= param', async () => {
  const LoginPage = await loadPage(true)
  m.getAccessToken.mockReturnValue('a-token')
  setUrl('/login?from=%2Fhandin')
  render(<LoginPage />)
  await waitFor(() => expect(m.replace).toHaveBeenCalledWith('/handin'))
})

it('bounces a cold signed-out visit straight to the gate, synchronously, with no API round-trips', async () => {
  const LoginPage = await loadPage(true)
  render(<LoginPage />)
  await waitFor(() => expect(assign).toHaveBeenCalledTimes(1))
  expect(assign.mock.calls[0][0]).toContain('/auth/oidc/login')
  // Regression guard: the ~1s flash was the /login page awaiting these before redirecting.
  expect(m.get).not.toHaveBeenCalledWith('/auth/oidc/config')
  expect(m.get).not.toHaveBeenCalledWith('/setup/status')
})

it('carries a from= through to the gate on a cold visit', async () => {
  const LoginPage = await loadPage(true)
  setUrl('/login?from=%2Fhandin')
  render(<LoginPage />)
  await waitFor(() => expect(assign).toHaveBeenCalledTimes(1))
  expect(assign.mock.calls[0][0]).toContain('from=%2Fhandin')
})

it('does not auto-bounce when the URL carries a gate error, and shows it instead', async () => {
  const LoginPage = await loadPage(true)
  setUrl('/login?error=gate_sign_in_expired')
  render(<LoginPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent('expired')
  expect(assign).not.toHaveBeenCalled()
})

it('falls back to the login form when the gate is not configured on this instance', async () => {
  const LoginPage = await loadPage(false)
  render(<LoginPage />)
  expect(await screen.findByLabelText('Email address')).toBeVisible()
  expect(assign).not.toHaveBeenCalled()
})

it('redirects to /setup when the gate is off and first-time setup is needed', async () => {
  const LoginPage = await loadPage(false)
  mockApi({ needsSetup: true })
  render(<LoginPage />)
  await waitFor(() => expect(m.replace).toHaveBeenCalledWith('/setup'))
  expect(assign).not.toHaveBeenCalled()
})
