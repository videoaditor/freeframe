import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { SWRConfig, useSWRConfig } from 'swr'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { PartsWorkspace } from '../parts-workspace'
import { requestIterations, type IterationProgress } from '@/lib/iterations'

vi.mock('@/lib/iterations', async original => ({ ...await original<typeof import('@/lib/iterations')>(), requestIterations: vi.fn() }))
const pending: IterationProgress = {
  enabled:true, mode:'components', submitted:true, can_leave:true, editor_done:false, state:'reviewing', delivered:0, total:1,
  manifest:{schema_version:1,summary:'',slots:[{id:'h',role:'hook',label:'Hook',script:'',group:''}],recipes:[]},
  slots:[{slot_id:'h',asset_id:'a',version_id:'v1',version_number:1,status:'ready',processing:'ready',findings:[],
    thumbnail_url:'/hook.jpg', review_progress:{stage:'waiting',version_id:'v1',elapsedSeconds:241}}], outputs:[],
}
function Recheck() {
  const { mutate } = useSWRConfig()
  return <button onClick={() => { void mutate(['parts','test']).catch(() => {}) }}>Recheck fixture</button>
}
const mount = () => render(<SWRConfig value={{provider:()=>new Map(),dedupingInterval:0,shouldRetryOnError:false}}><PartsWorkspace token="test" who={{name:'Fred',email:'fred@example.test'}} /><Recheck /></SWRConfig>)
beforeEach(() => { vi.mocked(requestIterations).mockReset(); vi.mocked(requestIterations).mockResolvedValue(pending) })
afterEach(cleanup)

it('uses authoritative processing and server elapsed in the existing part viewer', async () => {
  mount()
  fireEvent.click(await screen.findByRole('button',{name:'View feedback'}))
  expect(await screen.findByText('Waiting for review')).toBeVisible()
  expect(screen.getByText('4:01 elapsed')).toBeVisible()
  expect(screen.getByText('Measuring typical wait time')).toBeVisible()
  expect(screen.queryByText('Preparing video')).toBeNull()
})

it('does not treat a raw media URL as proof that transcoding is ready', async () => {
  vi.mocked(requestIterations).mockResolvedValue({...pending,slots:[{...pending.slots[0],processing:'processing',media_url:'/raw.mp4'}]})
  mount()
  fireEvent.click(await screen.findByRole('button',{name:'View feedback'}))
  expect(await screen.findByText('Preparing video')).toBeVisible()
})

it('stops cached activity after a failed status poll while keeping the still frame', async () => {
  mount()
  fireEvent.click(await screen.findByRole('button',{name:'View feedback'}))
  expect(await screen.findByRole('progressbar')).toBeVisible()
  vi.mocked(requestIterations).mockRejectedValue(new Error('Status unavailable'))
  fireEvent.click(screen.getByRole('button',{name:'Recheck fixture'}))
  expect(await screen.findByText('Review unavailable')).toBeVisible()
  expect(screen.queryByRole('progressbar')).toBeNull()
  expect(screen.getByAltText('Still frame of your submitted video')).toBeVisible()
  vi.mocked(requestIterations).mockResolvedValue(pending)
  fireEvent.click(screen.getByRole('button',{name:'Recheck fixture'}))
  expect(await screen.findByRole('progressbar')).toBeVisible()
})

it('does not invent a phase or time when older status responses omit progress', async () => {
  vi.mocked(requestIterations).mockResolvedValue({...pending,slots:[{...pending.slots[0],media_url:'/raw.mp4',review_progress:undefined}]})
  mount()
  fireEvent.click(await screen.findByRole('button',{name:'View feedback'}))
  expect(await screen.findByText('Waiting for review')).toBeVisible()
  expect(screen.getByText('Waiting time will appear when confirmed')).toBeVisible()
})

it('switches the part clock to the new exact version after replacement', async () => {
  mount()
  fireEvent.click(await screen.findByRole('button',{name:'View feedback'}))
  expect(await screen.findByText('4:01 elapsed')).toBeVisible()
  vi.mocked(requestIterations).mockResolvedValue({...pending,slots:[{...pending.slots[0],version_id:'v2',version_number:2,
    review_progress:{stage:'waiting',version_id:'v2',elapsedSeconds:4}}]})
  fireEvent.click(screen.getByRole('button',{name:'Recheck fixture'}))
  expect(await screen.findByText('0:04 elapsed')).toBeVisible()
})

it('shows an unknown output clock without blocking the final review view', async () => {
  vi.mocked(requestIterations).mockResolvedValue({...pending,outputs:[{id:'out',label:'Final ad',asset_id:'oa',version_id:'ov',
    status:'reviewing',processing:'ready',findings:[],review_progress:{stage:'waiting',version_id:'ov'}}]})
  mount()
  fireEvent.click(await screen.findByRole('button',{name:'View final review'}))
  expect(await screen.findByText('Waiting for review')).toBeVisible()
  expect(screen.getByText('Waiting time will appear when confirmed')).toBeVisible()
  expect(screen.queryByText(/\d+:\d+ elapsed/)).toBeNull()
  expect(screen.queryByRole('link',{name:'Download'})).toBeNull()
})
