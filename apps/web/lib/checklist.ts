import { api } from './api'
export interface RequirementSource { layer: 'basics' | 'brand' | 'briefing'; reference_id: string; source_version: string }
export interface ChecklistRequirement { id: string; text: string; severity: string; applicability: string; sources: RequirementSource[] }
export interface ChecklistState {
  id: string; status: 'queued' | 'preparing' | 'running' | 'ready' | 'failed'
  requirements: ChecklistRequirement[]; limitations: string[]; error_code?: string | null
  plan_id?: string | null; content_sha256?: string | null; trello_card_id?: string | null
}
export const prepareChecklist = (projectId: string, trelloUrl: string) => api.post<ChecklistState>('/checklists', { project_id: projectId, trello_url: trelloUrl })
export const getChecklist = (id: string) => api.get<ChecklistState>(`/checklists/${id}`)
export const retryChecklist = (id: string) => api.post<ChecklistState>(`/checklists/${id}/retry`)
export const checklistPollInterval = (data?: ChecklistState) => data && ['ready', 'failed'].includes(data.status) ? 0 : 3000

/** Preparation must wait for the picker when card metadata matches several workspaces. */
export function uniqueChecklistWorkspace<T extends {id:string;name:string;is_workspace?:boolean}>(projects:T[],brand:string,title:string):T|null {
  const norm=(s:string)=>s.toLowerCase().replace(/\bgmbh\b|\bug\b|\bco\b|\bkg\b|\bltd\b|\binc\b/g,'').replace(/[^a-z0-9]/g,'')
  const brandKey=norm(brand), hint=norm(brand+title)
  if (!hint) return null
  const matches=projects.filter(p=>{
    if (!p.is_workspace) return false
    const name=norm(p.name.replace(/ - workspace$/i,''))
    return name.length>2 && (hint.includes(name) || (!!brandKey && name.includes(brandKey)))
  })
  return matches.length===1?matches[0]:null
}
