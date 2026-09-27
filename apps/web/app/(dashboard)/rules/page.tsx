'use client'

/**
 * Brand rules (platform v2): write down what good means, once.
 *
 * Alan's playbook: briefing beats brand beats best practice, and the brand layer should reach 80%
 * in a second - drop the brand guide you already have. What the reviewer reads out of it arrives as
 * suggestions; nothing is live until the owner says yes. Rules learned from the owner's own comments
 * land in the same place.
 */
import * as React from 'react'
import useSWR from 'swr'
import { Check, X } from 'lucide-react'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth-store'
import { usePageTitle } from '@/hooks/use-page-title'
import { useToast } from '@/components/shared/toast'
import { decideSuggestion, fileToBase64, getRules, importRules } from '@/lib/platform'
import type { Project } from '@/types'
import { DropZone } from '@/components/v2/drop-zone'
import { cn } from '@/lib/utils'

export default function RulesPage() {
  usePageTitle('Brand rules')
  const user = useAuthStore((s) => s.user)
  const toast = useToast()
  const { data: projects } = useSWR<Project[]>('/projects', (k: string) => api.get<Project[]>(k))
  const brands = React.useMemo(
    () => (projects || []).filter((p) => user?.is_staff === false || p.is_workspace).sort((a, b) => a.name.localeCompare(b.name)),
    [projects, user],
  )
  const [pid, setPid] = React.useState('')
  React.useEffect(() => { if (!pid && brands.length) setPid(brands[0].id) }, [brands, pid])
  const { data, mutate, error } = useSWR(pid ? `/insights/rules?${pid}` : null, () => getRules(pid))
  const [reading, setReading] = React.useState(false)
  const [text, setText] = React.useState('')
  const [pasting, setPasting] = React.useState(false)

  const read = async (payload: { pdf_base64?: string; text?: string; url?: string }) => {
    setReading(true)
    try {
      const r = await importRules({ project_id: pid, ...payload })
      toast.success(r.drafted ? `${r.drafted} rules found. Check them below.` : 'Nothing new in there. Your rules already cover it.')
      setText(''); setPasting(false)
      mutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not read that. Try again.')
    } finally {
      setReading(false)
    }
  }

  const decide = async (id: string, action: 'accept' | 'dismiss') => {
    // Optimistic: it leaves the list at once; a failure puts it back and says so.
    mutate((d) => d && { ...d, suggestions: d.suggestions.filter((s) => s.id !== id) }, false)
    try { await decideSuggestion({ project_id: pid, suggestion_id: id, action }) }
    catch { toast.error('That did not save. It is back in the list.') }
    mutate()
  }

  const brandRules = (data?.rules || []).filter((r) => r.scope === 'brand' && r.active)
  const houseRules = (data?.rules || []).filter((r) => r.scope === 'global' && r.active)

  return (
    <div className="page-in mx-auto w-full max-w-4xl px-4 pb-20 pt-8 sm:px-8 sm:pt-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[34px] font-bold leading-tight tracking-[-0.02em] text-text-primary">Brand rules</h1>
          <p className="mt-1 max-w-xl text-[15px] text-text-secondary">What the reviewer checks every video against. The briefing always wins, then your brand, then our best practice.</p>
        </div>
        {brands.length > 1 && (
          <select value={pid} onChange={(e) => setPid(e.target.value)} className="field h-11 w-auto min-w-[200px]" aria-label="Brand">
            {brands.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        )}
      </div>

      {!brands.length && projects && (
        <p className="mt-10 text-[15px] text-text-secondary">Create a request first. Its brand appears here.</p>
      )}

      {pid && (
        <>
          <section className="mt-8">
            {pasting ? (
              <div className="glass space-y-3 p-5">
                <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} autoFocus className="field min-h-[132px] py-3 leading-relaxed"
                  placeholder="Paste your brand guide, or a Google Doc / Notion link" aria-label="Brand guide text or link" />
                <div className="flex justify-end gap-2">
                  <button type="button" onClick={() => setPasting(false)} className="press h-11 rounded-full px-5 text-[15px] font-medium text-text-secondary hover:bg-bg-hover">Cancel</button>
                  <button type="button" disabled={!text.trim() || reading}
                    onClick={() => read(/^https?:\/\//i.test(text.trim()) ? { url: text.trim() } : { text })}
                    className="press h-11 rounded-full bg-accent px-6 text-[15px] font-semibold text-text-inverse disabled:opacity-40">
                    {reading ? 'Reading…' : 'Find rules'}
                  </button>
                </div>
              </div>
            ) : (
              <div className={cn(reading && 'scan rounded-[var(--radius-xl)]')}>
                <DropZone compact accept="application/pdf" disabled={reading}
                  onFiles={async ([f]) => read({ pdf_base64: await fileToBase64(f) })}
                  title={reading ? 'Reading your guide…' : 'Drop your brand guide'}
                  hint="PDF · we read it and suggest rules, you decide" />
              </div>
            )}
            {!pasting && (
              <button type="button" onClick={() => setPasting(true)} className="mt-2 text-[13px] font-medium text-accent hover:underline">
                Paste text or a link instead
              </button>
            )}
          </section>

          {error && <p className="mt-6 text-[15px] text-status-error">The reviewer is not reachable right now. Try again in a minute.</p>}

          {!!data?.suggestions.length && (
            <section className="mt-10">
              <h2 className="mb-3 px-1 text-[13px] font-semibold uppercase tracking-[0.06em] text-accent">Waiting for you · {data.suggestions.length}</h2>
              <ul className="stagger space-y-2">
                {data.suggestions.map((s) => (
                  <li key={s.id} className="flex items-start gap-3 rounded-[var(--radius-lg)] border border-border bg-bg-secondary p-4">
                    <div className="min-w-0 flex-1">
                      <p className="text-[15px] font-semibold text-text-primary">{s.name}</p>
                      {s.what && <p className="mt-0.5 text-[15px] leading-relaxed text-text-secondary">{s.what}</p>}
                      {s.source === 'owner-comment' && <p className="mt-1 text-[12px] text-text-tertiary">Learned from your comments</p>}
                    </div>
                    <button type="button" onClick={() => decide(s.id, 'dismiss')} aria-label={`Dismiss ${s.name}`}
                      className="press grid h-11 w-11 shrink-0 place-items-center rounded-full text-text-tertiary hover:bg-bg-hover hover:text-text-primary">
                      <X className="h-4 w-4" />
                    </button>
                    <button type="button" onClick={() => decide(s.id, 'accept')}
                      className="press inline-flex h-11 shrink-0 items-center gap-1.5 rounded-full bg-bg-hover px-4 text-[15px] font-medium text-text-primary hover:bg-accent hover:text-text-inverse">
                      <Check className="h-4 w-4" /> Use
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <RuleGroup title="Your brand" empty="No brand rules yet. Drop your guide above." rules={brandRules} />
          <RuleGroup title="Our best practice" empty="" rules={houseRules} quiet />
        </>
      )}
    </div>
  )
}

function RuleGroup({ title, rules, empty, quiet }: { title: string; rules: { id: string; name: string; what: string; severity: string }[]; empty: string; quiet?: boolean }) {
  if (!rules.length && !empty) return null
  return (
    <section className="mt-10">
      <h2 className="mb-3 px-1 text-[13px] font-semibold uppercase tracking-[0.06em] text-text-secondary">{title} · {rules.length}</h2>
      {!rules.length ? <p className="px-1 text-[15px] text-text-tertiary">{empty}</p> : (
        <ul className={cn('divide-y divide-[var(--border-secondary)] overflow-hidden rounded-[var(--radius-lg)] border border-border', quiet ? 'bg-transparent' : 'bg-bg-secondary')}>
          {rules.map((r) => (
            <li key={r.id} className="flex items-start gap-3 px-4 py-3.5">
              <span className={cn('mt-2 h-1.5 w-1.5 shrink-0 rounded-full', r.severity === 'blocker' ? 'bg-status-error' : 'bg-text-tertiary')} aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="text-[15px] font-medium text-text-primary">{r.name}{r.severity === 'blocker' && <span className="ml-2 text-[12px] font-medium text-status-error">Must fix</span>}</p>
                {r.what && <p className="mt-0.5 line-clamp-2 text-[13px] leading-relaxed text-text-secondary">{r.what}</p>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
