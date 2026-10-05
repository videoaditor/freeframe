import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import GoogleCallbackPage from '../page'
import { GoogleButton } from '@/components/auth/google-button'
import { GOOGLE_STATE_KEY, googleAuthorizeUrl } from '@/lib/google-auth'

const m = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  setTokens: vi.fn(),
}))
vi.mock('@/lib/api', () => ({ api: { get: m.get, post: m.post }, ApiError: class ApiError extends Error { detail = 'no access' } }))
vi.mock('@/lib/auth', () => ({ setTokens: m.setTokens }))

const replace = vi.fn()
beforeEach(() => {
  sessionStorage.clear()
  vi.stubGlobal('location', { ...window.location, origin: 'https://feedback.aditor.ai', search: '', replace, assign: vi.fn() })
})
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks() })

it('builds the Google authorize URL for this origin', () => {
  const u = new URL(googleAuthorizeUrl('cid', 'https://feedback.aditor.ai', 's1'))
  expect(u.searchParams.get('redirect_uri')).toBe('https://feedback.aditor.ai/login/google')
  expect(u.searchParams.get('scope')).toBe('openid email')
  expect(u.searchParams.get('state')).toBe('s1')
})

it('hides the button until Google is configured', async () => {
  m.get.mockResolvedValue({ enabled: false, client_id: '' })
  const { container } = render(<GoogleButton />)
  await waitFor(() => expect(m.get).toHaveBeenCalledWith('/auth/google/config'))
  expect(container).toBeEmptyDOMElement()
})

it('shows the button when configured', async () => {
  m.get.mockResolvedValue({ enabled: true, client_id: 'cid' })
  render(<GoogleButton />)
  expect(await screen.findByRole('button', { name: /Continue with Google/ })).toBeVisible()
})

it('refuses a callback whose state does not match', async () => {
  sessionStorage.setItem(GOOGLE_STATE_KEY, 'expected')
  vi.stubGlobal('location', { ...window.location, origin: 'https://feedback.aditor.ai', search: '?code=c&state=forged', replace })
  render(<GoogleCallbackPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent('expired')
  expect(m.post).not.toHaveBeenCalled()
  expect(m.setTokens).not.toHaveBeenCalled()
})

it('trades the code and lands on /home', async () => {
  sessionStorage.setItem(GOOGLE_STATE_KEY, 'ok')
  vi.stubGlobal('location', { ...window.location, origin: 'https://feedback.aditor.ai', search: '?code=c&state=ok', replace })
  m.post.mockResolvedValue({ access_token: 'a', refresh_token: 'r' })
  render(<GoogleCallbackPage />)
  await waitFor(() => expect(replace).toHaveBeenCalledWith('/home'))
  expect(m.post).toHaveBeenCalledWith('/auth/google', { code: 'c', redirect_uri: 'https://feedback.aditor.ai/login/google' })
  expect(m.setTokens).toHaveBeenCalledWith('a', 'r')
})
