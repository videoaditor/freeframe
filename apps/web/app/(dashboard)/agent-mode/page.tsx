'use client'

/**
 * Agent Mode (spec 2026-11-05 H): the visible way in. Alan, 2026-11-07: "ich sehe noch keinen Agent-Mode"
 * - it lived only in Project → Settings → Agents. Same panel, now one tap from the main navigation.
 */
import * as React from 'react'
import useSWR from 'swr'
import { useRouter, useSearchParams } from 'next/navigation'
import { usePageTitle } from '@/hooks/use-page-title'
import { api } from '@/lib/api'
import { ConnectAgent } from '@/components/agents/connect-agent'
import type { Project } from '@/types'

// Agents are editors of one project, so only people who may add an editor see that project here.
const canConnect = (p: Project) => !p.role || p.role === 'owner' || p.role === 'editor'

function AgentMode() {
  usePageTitle('Agent Mode')
  const router = useRouter()
  const params = useSearchParams()
  const { data: projects, error, mutate } = useSWR<Project[]>('/projects', () => api.get<Project[]>('/projects'))
  const brands = (projects ?? []).filter(canConnect)
  const wanted = params.get('project')
  const projectId = brands.find(p => p.id === wanted)?.id ?? brands[0]?.id

  return (
    <div className="page-in mx-auto w-full max-w-2xl px-4 pb-24 pt-8 sm:px-8 sm:pt-12">
      <h1 className="text-[34px] font-bold leading-tight tracking-[-0.02em] text-text-primary">Agent Mode</h1>
      <p className="mt-2 text-[15px] text-text-secondary">Connect Claude Code, Codex, ChatGPT or Cursor. Your AI uploads cuts, reads the review and your feedback, and pushes the fix.</p>

      {error ? (
        <p role="alert" className="mt-8 text-sm text-text-secondary">Could not load your brands. <button className="min-h-11 font-medium text-accent" onClick={() => mutate()}>Retry</button></p>
      ) : !projects ? (
        <div className="skeleton-shimmer mt-8 h-64 animate-shimmer rounded-2xl" />
      ) : !projectId ? (
        <p className="mt-8 text-sm text-text-secondary">You need a brand you can edit before an AI can join it.</p>
      ) : (
        <div className="mt-8 space-y-6">
          {brands.length > 1 && (
            <div>
              <label htmlFor="agent-brand" className="text-sm font-medium text-text-primary">Brand</label>
              <select id="agent-brand" value={projectId} onChange={e => router.replace(`/agent-mode?project=${e.target.value}`)}
                className="mt-2 block h-11 w-full rounded-xl border border-border bg-bg-secondary px-3 text-[15px] text-text-primary sm:w-80">
                {brands.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <p className="mt-1.5 text-[0.8125rem] text-text-secondary">One key works for one brand only.</p>
            </div>
          )}
          <ConnectAgent key={projectId} projectId={projectId} />
        </div>
      )}
    </div>
  )
}

export default function AgentModePage() {
  return <React.Suspense fallback={null}><AgentMode /></React.Suspense>
}
