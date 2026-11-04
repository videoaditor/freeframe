import { describe, expect, it } from 'vitest'
import { notesReducer, sendable, sendBlocked, type FlowNote } from '../flow-notes'

const blob = new Blob(['x'])
const add = (s: FlowNote[], id: string, t: number) => notesReducer(s, { type: 'add', id, t })

describe('flow notes', () => {
  it('adds notes in timeline order, starting as recording', () => {
    const s = add(add([], 'b', 9), 'a', 3)
    expect(s.map(n => n.id)).toEqual(['a', 'b'])
    expect(s[0].status).toBe('recording')
  })
  it('goes recording -> transcribing -> ready and drops the audio', () => {
    let s = add([], 'a', 3)
    s = notesReducer(s, { type: 'transcribing', id: 'a', audio: blob })
    expect(s[0]).toMatchObject({ status: 'transcribing', audio: blob })
    s = notesReducer(s, { type: 'done', id: 'a', text: 'Hook too slow' })
    expect(s[0]).toMatchObject({ status: 'ready', text: 'Hook too slow' })
    expect(s[0].audio).toBeUndefined()
  })
  it('keeps the audio when transcription fails so Try again still works', () => {
    let s = add([], 'a', 3)
    s = notesReducer(s, { type: 'transcribing', id: 'a', audio: blob })
    s = notesReducer(s, { type: 'failed', id: 'a' })
    expect(s[0]).toMatchObject({ status: 'failed', audio: blob })
  })
  it('typing over a failed note makes it sendable', () => {
    let s = notesReducer(add([], 'a', 1), { type: 'failed', id: 'a' })
    expect(sendBlocked(s)).toBe(true)
    s = notesReducer(s, { type: 'edit', id: 'a', text: 'Cut earlier' })
    expect(sendBlocked(s)).toBe(false)
    expect(sendable(s)).toHaveLength(1)
  })
  it('blocks sending while recording or transcribing', () => {
    let s = add([], 'a', 1)
    expect(sendBlocked(s)).toBe(true)
    s = notesReducer(s, { type: 'transcribing', id: 'a', audio: blob })
    expect(sendBlocked(s)).toBe(true)
  })
  it('removes and clears', () => {
    const s = add(add([], 'a', 1), 'b', 2)
    expect(notesReducer(s, { type: 'remove', id: 'a' }).map(n => n.id)).toEqual(['b'])
    expect(notesReducer(s, { type: 'clear' })).toEqual([])
  })
})
