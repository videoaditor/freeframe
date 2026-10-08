import { it, expect } from 'vitest'
import { NextRequest } from 'next/server'
import { middleware } from '../../middleware'
import { clearTokens } from '../auth'
const from = '/handin?card=https%3A%2F%2Ftrello.com%2Fc%2FVUFKsrxi'
it.each(['email', 'whop'])('preserves the card through %s sign-in', async (provider) => {
  const request = new NextRequest('https://feedback.aditor.ai' + from, { headers: { cookie: 'ff_setup_done=1; ff_auth_provider=' + provider } })
  const response = await middleware(request)
  const target = new URL(response.headers.get('location')!)
  expect(target.pathname).toBe(provider === 'whop' ? '/whop' : '/login')
  expect(target.searchParams.get('from')).toBe(from)
})
it.each(['email', 'whop'])('preserves the card after an expired %s session', (provider) => {
  localStorage.setItem('ff_auth_provider', provider)
  Object.defineProperty(window, 'location', { value: { pathname: '/handin', search: from.slice(7), href: '' }, writable: true })
  clearTokens()
  const target = new URL(window.location.href, 'https://feedback.aditor.ai')
  // Non-Whop sign-out now routes through the gate logout endpoint first - it
  // forwards `from` and 302s to /login itself (ending any gate SSO session
  // too), which this unit test can't follow across the network.
  expect(target.pathname).toBe(provider === 'whop' ? '/whop' : '/auth/oidc/logout')
  expect(target.searchParams.get('from')).toBe(from)
})
