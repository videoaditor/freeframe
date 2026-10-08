import { describe, it, expect } from 'vitest'
import { handinCardFromSearch } from '../handin'

describe('Hub card handoff', () => {
  it('reads and canonicalizes a card without carrying tracking data', () => {
    const search = '?card=' + encodeURIComponent('https://trello.com/c/VUFKsrxi/example?tracking=1')
    expect(handinCardFromSearch(search)).toBe('https://trello.com/c/VUFKsrxi')
  })
  it('leaves ordinary or invalid handoffs blank', () => {
    expect(handinCardFromSearch('')).toBe('')
    for (const url of ['javascript:alert(1)', 'https://trello.com.evil.test/c/VUFKsrxi', 'https://user@trello.com/c/VUFKsrxi', 'https://trello.com/b/VUFKsrxi', 'http://trello.com/c/VUFKsrxi']) {
      expect(handinCardFromSearch('?card='+encodeURIComponent(url))).toBe('')
    }
  })
})

import { handinReturnPath } from '../handin'
it('allows the exact onboarding return path without widening the redirect allowlist', () => {
  expect(handinReturnPath('?from=%2Fstart')).toBe('/start')
  for (const from of ['/start/../admin', '/start?next=https://evil.test', '//evil.test/start', 'https://evil.test/start']) {
    expect(handinReturnPath('?from=' + encodeURIComponent(from))).toBe('/home')
  }
})
it('returns Whop sign-in only to a valid Hub hand-in', () => {
  expect(handinReturnPath('?from='+encodeURIComponent('/handin?card=https://trello.com/c/VUFKsrxi'))).toBe('/handin?card=https%3A%2F%2Ftrello.com%2Fc%2FVUFKsrxi')
  for (const from of ['https://evil.test/handin?card=x', '//evil.test', '/handin?card=https://evil.test/c/VUFKsrxi', '/admin']) {
    expect(handinReturnPath('?from='+encodeURIComponent(from))).toBe('/home')
  }
})

it('does not guess a workspace when the card matches several workspaces', async () => {
  const { uniqueChecklistWorkspace } = await import('../checklist')
  const projects = [{id:'a',name:'Studio',is_workspace:true},{id:'b',name:'Studio - Workspace',is_workspace:true}]
  expect(uniqueChecklistWorkspace(projects,'Studio','Launch')).toBeNull()
  expect(uniqueChecklistWorkspace(projects,'','Launch')).toBeNull()
  expect(uniqueChecklistWorkspace(projects.slice(0,1),'Studio','Launch')?.id).toBe('a')
})
