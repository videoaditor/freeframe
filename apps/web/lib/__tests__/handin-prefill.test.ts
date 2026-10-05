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
