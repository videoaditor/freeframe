import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {SWRConfig} from 'swr'
import {afterEach,expect,it,vi} from 'vitest'
import {PartsHandin} from '../parts-handin'
import {createPartHandin} from '@/lib/iterations'
vi.mock('@/lib/iterations',()=>({createPartHandin:vi.fn()}))
vi.mock('@/lib/api',()=>({api:{get:async()=>[{id:'project',name:'Brand',is_workspace:true,role:'owner'}]}}))
vi.mock('@/lib/platform',()=>({viewRequest:async()=>({brand:'Brand'})}))
vi.mock('@/stores/auth-store',()=>({useAuthStore:(selector:any)=>selector({user:{is_staff:true}})}))
vi.mock('../workspace-picker',()=>({WorkspacePicker:({onChange}:any)=><button type="button" onClick={()=>onChange({kind:'existing',id:'project',name:'Brand'})}>Select Brand</button>}))
vi.mock('@/components/v2/parts-workspace',()=>({PartsWorkspace:()=> <div>Uploaded workspace</div>}))
afterEach(()=>{cleanup();vi.clearAllMocks();window.history.replaceState(null,'','/handin')})
it('reuses the same operation identity after an ambiguous creation response',async()=>{
 vi.mocked(createPartHandin).mockRejectedValueOnce(Error('Response lost')).mockResolvedValueOnce({token:'native'})
 render(<SWRConfig value={{provider:()=>new Map()}}><PartsHandin/></SWRConfig>)
 fireEvent.change(screen.getByLabelText('Trello card'),{target:{value:'https://trello.com/c/AbCd1234'}})
 fireEvent.click(screen.getByText('Select Brand'));fireEvent.click(screen.getByText('Continue to upload'))
 await screen.findByRole('alert');fireEvent.click(screen.getByText('Continue to upload'))
 await waitFor(()=>expect(createPartHandin).toHaveBeenCalledTimes(2))
 const calls=vi.mocked(createPartHandin).mock.calls
 expect(calls[0][2]).toMatch(/^[a-f0-9-]{36}$/);expect(calls[1][2]).toBe(calls[0][2])
})
