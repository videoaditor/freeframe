import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { LoginForm } from '../login-form'

const m = vi.hoisted(() => ({get:vi.fn(),post:vi.fn(),replace:vi.fn()}))
vi.mock('next/navigation',()=>({useRouter:()=>({replace:m.replace})}))
vi.mock('@/lib/api',()=>({api:{get:m.get,post:m.post},ApiError:class extends Error {detail='Failed'}}))
vi.mock('@/lib/auth',()=>({setTokens:vi.fn()}))
vi.mock('@/stores/auth-store',()=>({useAuthStore:{getState:()=>({fetchUser:vi.fn(),user:null})}}))

function mockGate(enabled: boolean) {
  m.get.mockImplementation((url: string) =>
    url === '/auth/oidc/config' ? Promise.resolve({ enabled }) : Promise.resolve({}))
}

beforeEach(()=>{
 vi.stubEnv('NEXT_PUBLIC_PASSWORD_LOGIN_ENABLED','false')
 vi.stubEnv('NEXT_PUBLIC_LEGACY_LOGIN_ENABLED','false')
 window.history.replaceState({},'', '/login')
 mockGate(true)
 m.post.mockResolvedValue({})
})
afterEach(()=>{vi.clearAllMocks();vi.unstubAllEnvs()})

it('shows only Sign in with Aditor when the gate is configured',async()=>{
 render(<LoginForm />)
 expect(await screen.findByRole('button',{name:'Sign in with Aditor'})).toBeVisible()
 expect(screen.queryByRole('button',{name:'Continue with Google'})).not.toBeInTheDocument()
 expect(screen.queryByLabelText('Email address')).not.toBeInTheDocument()
})

it('falls back to the email flow when the gate is not configured',async()=>{
 mockGate(false)
 render(<LoginForm />)
 expect(await screen.findByLabelText('Email address')).toBeVisible()
 expect(screen.queryByRole('button',{name:'Sign in with Aditor'})).not.toBeInTheDocument()
 expect(screen.queryByRole('button',{name:'Continue with Google'})).not.toBeInTheDocument()
})

it('reveals the legacy email flow alongside the gate when LEGACY_LOGIN_ENABLED is on',async()=>{
 vi.stubEnv('NEXT_PUBLIC_LEGACY_LOGIN_ENABLED','true')
 render(<LoginForm />)
 expect(await screen.findByRole('button',{name:'Sign in with Aditor'})).toBeVisible()
 expect(await screen.findByLabelText('Email address')).toBeVisible()
})

it('opens the email flow directly for an explicit prefilled email link, gate notwithstanding',async()=>{
 window.history.replaceState({},'', '/login?email=editor%40example.com')
 render(<LoginForm />)
 expect(await screen.findByLabelText('Email address')).toHaveValue('editor@example.com')
})

it('shows gate failure errors on the primary gate screen',async()=>{
 window.history.replaceState({},'', '/login?error=gate_sign_in_expired')
 render(<LoginForm />)
 expect(await screen.findByRole('alert')).toHaveTextContent('expired')
})

it('sends a magic code once the legacy email flow is reached',async()=>{
 mockGate(false)
 render(<LoginForm />)
 fireEvent.change(await screen.findByLabelText('Email address'),{target:{value:'editor@example.com'}})
 fireEvent.click(screen.getByRole('button',{name:'Send sign-in code'}))
 await waitFor(()=>expect(m.post).toHaveBeenCalledWith('/auth/send-magic-code',{email:'editor@example.com'}))
 expect(await screen.findByText('Check your email')).toBeVisible()
})
