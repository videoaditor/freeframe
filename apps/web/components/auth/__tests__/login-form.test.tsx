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
 vi.stubEnv('NEXT_PUBLIC_PASSWORD_LOGIN_ENABLED','true')
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

it('falls back to the password form when the gate is not configured',async()=>{
 mockGate(false)
 render(<LoginForm />)
 expect(await screen.findByLabelText('Email address')).toBeVisible()
 expect(screen.getByLabelText('Password')).toBeVisible()
 expect(screen.queryByRole('button',{name:'Sign in with Aditor'})).not.toBeInTheDocument()
 expect(screen.queryByRole('button',{name:'Continue with Google'})).not.toBeInTheDocument()
})

it('reveals the legacy password form alongside the gate when LEGACY_LOGIN_ENABLED is on',async()=>{
 vi.stubEnv('NEXT_PUBLIC_LEGACY_LOGIN_ENABLED','true')
 render(<LoginForm />)
 expect(await screen.findByRole('button',{name:'Sign in with Aditor'})).toBeVisible()
 expect(await screen.findByLabelText('Email address')).toBeVisible()
})

it('shows gate failure errors on the primary gate screen',async()=>{
 window.history.replaceState({},'', '/login?error=gate_sign_in_expired')
 render(<LoginForm />)
 expect(await screen.findByRole('alert')).toHaveTextContent('expired')
})

it('hides the password form entirely when password login is disabled, even with no gate',async()=>{
 vi.stubEnv('NEXT_PUBLIC_PASSWORD_LOGIN_ENABLED','false')
 mockGate(false)
 render(<LoginForm />)
 await waitFor(()=>expect(m.get).toHaveBeenCalledWith('/auth/oidc/config'))
 expect(screen.queryByLabelText('Email address')).not.toBeInTheDocument()
})

it('signs in with the classic password form once reached',async()=>{
 mockGate(false)
 render(<LoginForm />)
 fireEvent.change(await screen.findByLabelText('Email address'),{target:{value:'editor@example.com'}})
 fireEvent.change(screen.getByLabelText('Password'),{target:{value:'hunter2'}})
 fireEvent.click(screen.getByRole('button',{name:'Sign in'}))
 await waitFor(()=>expect(m.post).toHaveBeenCalledWith('/auth/login',{email:'editor@example.com',password:'hunter2'}))
 await waitFor(()=>expect(m.replace).toHaveBeenCalledWith('/home'))
})
