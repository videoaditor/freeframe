import { describe, it, expect, vi, afterEach } from 'vitest'
import { lookUpCard, fetchReview } from '../handin'

/**
 * The gate client. Both endpoints exist to help an editor hand in, so neither
 * is allowed to turn a bad day at the review service into a blocked upload.
 */
describe('looking up a Trello card', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('returns the name and brand so the editor types neither', () => {
    // Misfiled projects came from typed brand names. The card is the authority.
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({ name: 'BATCH#66_Stuck Belly Fat', brand: 'beinfit-swivy', hasBriefing: true }),
    })) as unknown as typeof fetch)

    return lookUpCard('https://trello.com/c/stNBviIk').then((card) => {
      expect(card.name).toBe('BATCH#66_Stuck Belly Fat')
      expect(card.brand).toBe('beinfit-swivy')
    })
  })

  it('answers calmly when the gate is unreachable rather than throwing', async () => {
    // A thrown error here surfaces as "something is wrong with your card, do
    // not upload", which is the opposite of true. The honest meaning is "I
    // could not look it up - upload anyway". The upload must never wait on
    // Trello being up.
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('network down') }) as unknown as typeof fetch)
    const card = await lookUpCard('https://trello.com/c/stNBviIk')
    expect(card.note).toMatch(/Upload anyway/)
    expect(card.hasBriefing).toBe(false)
  })

  it('treats a 5xx from the gate the same calm way', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 500 })) as unknown as typeof fetch)
    const card = await lookUpCard('https://trello.com/c/stNBviIk')
    expect(card.note).toMatch(/Upload anyway/)
  })
})

describe('fetching the review', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('passes a ready review through with both groups', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({ state: 'ready', score: 70, worthFixing: ['CTA missing.'], niceToHave: ['Music bed.'] }),
    })) as unknown as typeof fetch)

    const review = await fetchReview('a1')
    expect(review.state).toBe('ready')
    if (review.state === 'ready') {
      expect(review.worthFixing).toEqual(['CTA missing.'])
      expect(review.niceToHave).toEqual(['Music bed.'])
    }
  })

  it('reports a dead review service as pending, never as an error', async () => {
    // The page renders the link regardless, but an error state is still the
    // wrong word: it invites a future reader to treat "review failed" as a
    // condition worth acting on. There is no failure state here to act on.
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('gone') }) as unknown as typeof fetch)
    const review = await fetchReview('a1')
    expect(review.state).toBe('pending')
  })

  it('escapes the asset id rather than pasting it into the query string', async () => {
    const spy = vi.fn(async (_url: string) => ({ ok: true, json: async () => ({ state: 'pending' }) }))
    vi.stubGlobal('fetch', spy as unknown as typeof fetch)
    await fetchReview('a 1&x=2')
    expect(String(spy.mock.calls[0]?.[0])).toContain('asset=a%201%26x%3D2')
  })
})
