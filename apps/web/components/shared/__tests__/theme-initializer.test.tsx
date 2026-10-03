import { render, cleanup } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
const apply = vi.hoisted(() => vi.fn())
vi.mock('@/stores/theme-store', () => {
  const state = { theme: 'dark', applyTheme: apply, syncFromServer: vi.fn() }
  return { useThemeStore: Object.assign((select: (s: typeof state) => unknown) => select(state), { getState: () => ({ ...state, theme: 'light' }) }) }
})
vi.mock('@/stores/auth-store', () => ({ useAuthStore: (select: (s: { user: null }) => unknown) => select({ user: null }) }))
import { ThemeInitializer } from '../theme-initializer'
afterEach(cleanup)
it('uses the hydrated theme rather than a stale first-render default on navigation', () => {
  render(<ThemeInitializer />)
  expect(apply).toHaveBeenCalledWith('light')
})
