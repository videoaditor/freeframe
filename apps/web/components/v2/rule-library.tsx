'use client'

import * as React from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { ArrowUpRight, BookOpen, Search, ShieldCheck, SlidersHorizontal, X } from 'lucide-react'
import type { RuleRow } from '@/lib/platform'
import { cn } from '@/lib/utils'

const FILTERS = ['All', 'Must follow', 'Guidance'] as const

export function RuleLibrary({ rules, brandName, onAdd }: { rules: RuleRow[]; brandName: string; onAdd: () => void }) {
  const [query, setQuery] = React.useState('')
  const [filter, setFilter] = React.useState<typeof FILTERS[number]>('All')
  const [selected, setSelected] = React.useState<RuleRow | null>(null)
  const visible = rules.filter(r => (filter === 'All' || (r.severity === 'blocker') === (filter === 'Must follow')) && `${r.name} ${r.what}`.toLowerCase().includes(query.trim().toLowerCase()))

  return <section aria-label="Brand playbook">
    <div className="flex items-baseline justify-between gap-3"><h2 className="text-xl font-semibold tracking-tight">Your rules</h2><span className="text-[0.8125rem] text-text-secondary">{rules.length} active</span></div>
    {!!rules.length && <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
      <div className="flex gap-1" aria-label="Filter rules">{FILTERS.map(f => <button type="button" key={f} aria-pressed={filter === f} onClick={() => setFilter(f)} className={cn('press min-h-11 rounded-full px-3 text-[0.8125rem] font-medium', filter === f ? 'bg-text-primary text-bg-primary' : 'text-text-secondary hover:bg-bg-hover')}>{f}</button>)}</div>
      <label className="flex h-11 w-full items-center gap-2 rounded-full border border-border bg-bg-secondary px-3 sm:w-48"><Search size={15} className="shrink-0 text-text-secondary" /><input aria-label="Search rules" placeholder="Find a rule" value={query} onChange={e => setQuery(e.target.value)} className="min-w-0 w-full bg-transparent text-[0.875rem] outline-none" /></label>
    </div>}
    {!rules.length ? <div className="playbook-empty mt-5">
      <div className="playbook-empty-icon" aria-hidden="true"><BookOpen size={28} /></div>
      <h3 className="mt-5 text-xl font-semibold tracking-tight">Make it unmistakably {brandName}.</h3>
      <p className="mx-auto mt-2 max-w-sm text-[0.9375rem] leading-relaxed text-text-secondary">Bring your guide. Turn the details that matter into rules for every cut.</p>
      <button type="button" onClick={onAdd} className="press mt-5 min-h-11 rounded-full bg-accent px-5 text-[0.875rem] font-semibold text-text-inverse">Add your first guidelines</button>
    </div> : visible.length ? <ul className="rule-grid mt-5" aria-label="Active brand rules">{visible.map(r => <li key={r.id}>
      <button type="button" onClick={() => setSelected(r)} className="rule-card" data-required={r.severity === 'blocker'} aria-label={`View rule: ${r.name}`}>
        <div className="flex items-center justify-between gap-3"><span className="rule-number">{String(rules.indexOf(r) + 1).padStart(2, '0')}</span><RuleSeverity rule={r} /></div>
        <h3 className="mt-3 text-[1.0625rem] font-semibold leading-snug tracking-tight">{r.name}</h3>
        <span className="mt-3 text-[0.75rem] font-medium text-text-secondary">Review check</span>
        <p className="mt-1 line-clamp-2 whitespace-pre-line text-[0.875rem] leading-relaxed text-text-secondary">{r.what || 'Open for rule details.'}</p>
        <span className="rule-card-open">View rule <ArrowUpRight size={15} /></span>
      </button>
    </li>)}</ul> : <div className="playbook-empty mt-5"><p className="text-text-secondary">No matching rules</p><button type="button" onClick={() => { setQuery(''); setFilter('All') }} className="mt-2 min-h-11 font-medium text-accent">Clear filters</button></div>}
    <Dialog.Root open={!!selected} onOpenChange={open => { if (!open) setSelected(null) }}>
      <Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm" /><Dialog.Content className="owner-sheet playbook-dialog sheet-in">
        <div className="flex items-start justify-between gap-4"><div className="min-w-0"><p className="mb-3 text-[0.8125rem] text-text-secondary">{brandName} · Brand rule</p><Dialog.Title className="break-words text-2xl font-semibold tracking-tight">{selected?.name}</Dialog.Title></div><Dialog.Close aria-label="Close rule" className="press grid h-11 w-11 shrink-0 place-items-center rounded-full hover:bg-bg-hover"><X size={20} /></Dialog.Close></div>
        {selected && <div className="mt-4"><RuleSeverity rule={selected} /></div>}
        <p className="mt-6 text-[0.75rem] font-medium text-text-secondary">Review check</p>
        <Dialog.Description className="mt-2 whitespace-pre-wrap break-words text-[1rem] leading-relaxed [overflow-wrap:anywhere]">{selected?.what || 'No additional guidance for this rule.'}</Dialog.Description>
        <p className="mt-8 border-t border-border pt-4 text-[0.8125rem] text-text-secondary">Applies to this brand. A project’s briefing takes priority.</p>
        <Dialog.Close className="press mt-5 min-h-11 w-full rounded-full bg-accent px-5 font-medium text-text-inverse">Done</Dialog.Close>
      </Dialog.Content></Dialog.Portal>
    </Dialog.Root>
  </section>
}

export function RuleSeverity({ rule }: { rule: Pick<RuleRow, 'severity'> }) {
  const required = rule.severity === 'blocker'
  const Icon = required ? ShieldCheck : SlidersHorizontal
  return <span className={cn('rule-severity', required && 'rule-severity-required')}><Icon size={13} />{required ? 'Must follow' : 'Guidance'}</span>
}
