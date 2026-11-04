import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import {
  PROGRAM_LABEL, countdown, mcpAddCommand, pairInstruction, programLabel,
  createPairingCode, listAgents, revokeAgent, setAgentsMayApprove,
  closeRound, roundSummary, formatSent, type FeedbackV1,
} from '../agents'

afterEach(() => vi.restoreAllMocks())

describe('programLabel', () => {
  it('names every contract program and falls back to Other', () => {
    expect(PROGRAM_LABEL['claude-code']).toBe('Claude Code')
    expect(programLabel('codex')).toBe('Codex')
    expect(programLabel('hermes')).toBe('Hermes')
    expect(programLabel('grok')).toBe('Grok')
    expect(programLabel('other')).toBe('Other')
    expect(programLabel('something-new')).toBe('Other')
    expect(programLabel(null)).toBeNull()
  })
})

describe('countdown', () => {
  const now = Date.parse('2026-11-04T10:00:00Z')
  it('formats mm:ss until expiry', () => {
    expect(countdown('2026-11-04T10:14:30Z', now)).toEqual({ label: '14:30', expired: false })
    expect(countdown('2026-11-04T10:00:05Z', now)).toEqual({ label: '0:05', expired: false })
  })
  it('flags expiry and never goes negative', () => {
    expect(countdown('2026-11-04T09:59:00Z', now)).toEqual({ label: '0:00', expired: true })
  })
})

describe('copy block', () => {
  it('builds the MCP add command and the pairing sentence', () => {
    expect(mcpAddCommand('https://review.aditor.ai/mcp')).toBe('claude mcp add --transport http autoreview https://review.aditor.ai/mcp')
    expect(pairInstruction('ABCD2345')).toBe('Pair with code ABCD2345')
  })
})

describe('REST wrappers', () => {
  it('hits the contract paths', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ code: 'ABCD2345', expires_at: 'x' })
    const get = vi.spyOn(api, 'get').mockResolvedValue([])
    const del = vi.spyOn(api, 'delete').mockResolvedValue(undefined)
    const patch = vi.spyOn(api, 'patch').mockResolvedValue({})
    await createPairingCode('p1')
    await listAgents('p1')
    await revokeAgent('p1', 'u1')
    await setAgentsMayApprove('p1', true)
    expect(post).toHaveBeenCalledWith('/projects/p1/agent-pairing-codes')
    expect(get).toHaveBeenCalledWith('/projects/p1/agents')
    expect(del).toHaveBeenCalledWith('/projects/p1/agents/u1')
    expect(patch).toHaveBeenCalledWith('/projects/p1', { agents_may_approve: true })
  })
  it('closes a round with reason button', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({})
    await closeRound('r1')
    expect(post).toHaveBeenCalledWith('/requests/r1/feedback-rounds/close', { reason: 'button' })
  })
})

describe('round summary', () => {
  const round = {
    files: [{ comments: [{}, {}] }, { comments: [{}] }, { comments: [] }],
  } as unknown as FeedbackV1
  it('counts comments across files', () => {
    expect(roundSummary(round)).toBe(3)
  })
  it('words the success line', () => {
    expect(formatSent('Claude Code', 3)).toBe('Sent to Claude Code · 3 comments')
    expect(formatSent('Codex', 1)).toBe('Sent to Codex · 1 comment')
  })
})
