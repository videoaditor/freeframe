import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { LoginForm } from '../login-form'

const m = vi.hoisted(() => ({get:vi.fn(),post:vi.fn(),replace:vi.fn()}))
vi.mock('next/navigation',()=>({useRouter:()=>({replace:m.replace})}))
vi.mock('@/lib/api',()=>({api:{get:m.get,post:m.post},ApiError:class extends Error {detail='Failed'}}))
vi.mock('@/lib/auth',()=>({setTokens:vi.fn()}))
vi.mock('@/stores/auth-store',()=>({useAuthStore:{getState:()=>({fetchUser:vi.fn(),user:null})}}))
beforeEach(()=>{
 vi.stubEnv('NEXT_PUBLIC_PASSWORD_LOGIN_ENABLED','false')
 window.history.replaceState({},'', '/login')
 m.get.mockResolvedValue({enabled:true,client_id:'google-client'})
 m.post.mockResolvedValue({})
})
afterEach(()=>{vi.clearAllMocks();vi.unstubAllEnvs()})

it('makes Google primary and discloses email only when requested',async()=>{
 render(<LoginForm />)
 expect(await screen.findByRole('button',{name:'Continue with Google'})).toBeVisible()
 expect(screen.queryByLabelText('Email address')).not.toBeInTheDocument()
 expect(screen.queryByText('Sign in with Aditor')).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'Use email instead'}))
 expect(screen.getByLabelText('Email address')).toBeVisible()
 expect(screen.getByLabelText('Email address')).toHaveFocus()
 fireEvent.change(screen.getByLabelText('Email address'),{target:{value:'editor@example.com'}})
 fireEvent.click(screen.getByRole('button',{name:'Send sign-in code'}))
 await waitFor(()=>expect(m.post).toHaveBeenCalledWith('/auth/send-magic-code',{email:'editor@example.com'}))
 expect(await screen.findByText('Check your email')).toBeVisible()
})
it.each(['disabled','error'])('keeps email usable when Google config is %s',async(reason)=>{
 if(reason==='error')m.get.mockRejectedValue(new Error('offline'))
 else m.get.mockResolvedValue({enabled:false,client_id:''})
 render(<LoginForm />)
 expect(await screen.findByLabelText('Email address')).toBeVisible()
 expect(screen.queryByRole('button',{name:'Continue with Google'})).not.toBeInTheDocument()
})
it('opens email for an explicit prefilled email link',async()=>{
 window.history.replaceState({},'', '/login?email=editor%40example.com')
 render(<LoginForm />)
 expect(await screen.findByLabelText('Email address')).toHaveValue('editor@example.com')
})

it('lets people use email while provider discovery is slow',async()=>{
 m.get.mockReturnValue(new Promise(()=>{}))
 render(<LoginForm />)
 fireEvent.click(screen.getByRole('button',{name:'Use email instead'}))
 expect(screen.getByLabelText('Email address')).toBeVisible()
})
it('shows sign-in errors even with email collapsed',async()=>{
 window.history.replaceState({},'', '/login?error=gate_sign_in_expired')
 render(<LoginForm />)
 expect(await screen.findByRole('alert')).toHaveTextContent('expired')
})
