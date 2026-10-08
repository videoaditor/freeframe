import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'
import { SWRConfig } from 'swr'
import { ChecklistPanel, SavedChecklist, useChecklistPreparation } from '../checklist'
import { api, ApiError } from '@/lib/api'

vi.mock('@/lib/api', async original => ({ ...await original<typeof import('@/lib/api')>(), api: { get: vi.fn(), post: vi.fn() } }))
afterEach(() => { cleanup(); vi.resetAllMocks() })
const ready = { id: 'binding-a', status: 'ready' as const, requirements: [{ id:'r1', text:'Keep the product visible.', severity:'warning', applicability:'video', sources:[{layer:'brand' as const,reference_id:'r1',source_version:'v1'}] }], limitations:[] }
const wrapper=({children}:{children:React.ReactNode})=><SWRConfig value={{provider:()=>new Map(),dedupingInterval:0}}>{children}</SWRConfig>
it('shows a quiet pending state while the upload link remains usable', () => {
  render(<><a href='/r/test'>Upload link</a><ChecklistPanel data={{id:'a',status:'queued',requirements:[],limitations:[]}} /></>)
  expect(screen.getByText('Preparing review checklist…')).toBeVisible()
  expect(screen.getByRole('link',{name:'Upload link'})).toHaveAttribute('href','/r/test')
})
it('shows source and submission scope without turning the checklist into a pass', () => {
  render(<ChecklistPanel data={{...ready,requirements:[{...ready.requirements[0],applicability:'submission'}]}} />)
  fireEvent.click(screen.getByText('1 review check'))
  expect(screen.getByText('Brand')).toBeVisible()
  expect(screen.getByText('Whole submission')).toBeVisible()
  expect(screen.queryByText(/passed/i)).toBeNull()
})
it('offers retry on failure and refuses an empty ready list', () => {
  const retry=vi.fn(); const view=render(<ChecklistPanel data={{id:'a',status:'failed',requirements:[],limitations:[],error_code:'plan-api-unavailable'}} onRetry={retry} />)
  fireEvent.click(screen.getByRole('button',{name:'Try again'})); expect(retry).toHaveBeenCalledOnce()
  view.rerender(<ChecklistPanel data={{...ready,requirements:[]}} />)
  expect(screen.getByText(/Checklist unavailable/)).toBeVisible()
  expect(screen.queryByText('0 review checks')).toBeNull()
})
it('prepares once for paste/blur and ignores a late A response after B selection', async () => {
  let finishA!:(v:unknown)=>void
  vi.mocked(api.post).mockImplementationOnce(()=>new Promise(r=>{finishA=r})).mockResolvedValueOnce({...ready,id:'binding-b'})
  const {result,rerender}=renderHook(({url})=>useChecklistPreparation('project-a',url),{initialProps:{url:'https://trello.com/c/AAAA1111'},wrapper})
  await waitFor(()=>expect(api.post).toHaveBeenCalledTimes(1))
  rerender({url:'https://trello.com/c/AAAA1111'}); expect(api.post).toHaveBeenCalledTimes(1)
  rerender({url:'https://trello.com/c/BBBB2222'});
  await waitFor(()=>expect(result.current.data?.id).toBe('binding-b'))
  await act(async()=>finishA(ready)); expect(result.current.data?.id).toBe('binding-b')
})
it('waits for a workspace before starting paid preparation', () => {
  renderHook(()=>useChecklistPreparation(null,'https://trello.com/c/AAAA1111'),{wrapper})
  expect(api.post).not.toHaveBeenCalled()
})
it('clears a confirmed conflict only after successful preparation', async () => {
  vi.mocked(api.post).mockRejectedValue(new ApiError(409,'Create a new request'))
  const {result}=renderHook(()=>useChecklistPreparation('project-a','https://trello.com/c/AAAA1111'),{wrapper})
  await waitFor(()=>expect(result.current.conflict?.status).toBe(409))
  vi.mocked(api.post).mockRejectedValue(new ApiError(503,'Preparation unavailable'))
  await act(async()=>{ await result.current.mutate() })
  expect(result.current.conflict?.status).toBe(409)
  vi.mocked(api.post).mockResolvedValue(ready)
  await act(async()=>{ await result.current.mutate() })
  expect(result.current.conflict).toBeNull()
  expect(result.current.data).toEqual(ready)
})
it('does not carry a confirmed conflict into a different card', async () => {
  vi.mocked(api.post).mockRejectedValue(new ApiError(409,'Create a new request'))
  const {result,rerender}=renderHook(({url})=>useChecklistPreparation('project-a',url),{initialProps:{url:'https://trello.com/c/AAAA1111'},wrapper})
  await waitFor(()=>expect(result.current.conflict?.status).toBe(409))
  vi.mocked(api.post).mockRejectedValue(new ApiError(503,'Preparation unavailable'))
  rerender({url:'https://trello.com/c/BBBB2222'})
  await waitFor(()=>expect(result.current.error?.status).toBe(503))
  expect(result.current.conflict).toBeNull()
})
it('reload reads the saved checklist and stops polling after ready', async () => {
  vi.mocked(api.get).mockResolvedValue(ready)
  render(<SavedChecklist bindingId='binding-a' />,{wrapper})
  expect(await screen.findByText('1 review check')).toBeVisible()
  expect(api.get).toHaveBeenCalledWith('/checklists/binding-a')
})

it('shows a failed retry without losing the saved checklist or rejecting unhandled', async () => {
  vi.mocked(api.get).mockResolvedValue({...ready,status:'failed',error_code:'plan-api-unavailable'})
  vi.mocked(api.post).mockRejectedValue(new Error('offline'))
  render(<SavedChecklist bindingId='binding-a' />,{wrapper})
  fireEvent.click(await screen.findByRole('button',{name:'Try again'}))
  expect(await screen.findByText('The checklist could not be retried. Try again.')).toBeVisible()
})
it('does not show an old retry failure on a newly selected saved checklist',async()=>{
  let failA!:(reason:Error)=>void
  vi.mocked(api.get).mockImplementation(async(path)=>path.includes('binding-a')?{...ready,status:'failed'}:{...ready,id:'binding-b'})
  vi.mocked(api.post).mockImplementation(()=>new Promise((_,reject)=>{failA=reject}))
  const view=render(<SavedChecklist bindingId='binding-a' />,{wrapper})
  fireEvent.click(await screen.findByRole('button',{name:'Try again'}))
  view.rerender(<SavedChecklist bindingId='binding-b' />)
  await screen.findByText('1 review check')
  await act(async()=>failA(new Error('late failure')))
  expect(screen.getByText('1 review check')).toBeVisible()
  expect(screen.queryByText('The checklist could not be retried. Try again.')).toBeNull()
})
