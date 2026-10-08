'use client'

import * as React from 'react'
import Image from 'next/image'
import * as Select from '@radix-ui/react-select'
import { useRouter } from 'next/navigation'
import useSWR, { useSWRConfig } from 'swr'
import { ArrowLeft, ArrowRight, BookOpen, Check, ChevronDown, FileText, Link2, ScanLine, Sparkles, X } from 'lucide-react'
import type { Project, User } from '@/types'
import { api } from '@/lib/api'
import { ownsProject } from '@/lib/workspace-access'
import { canSetUpAutoReview, setupProgress, type SetupProgress } from '@/lib/onboarding'
import { BRIEFING_ACCEPT, briefingFilePayload } from '@/lib/briefing'
import { createRequest, decideSuggestion, getRules, importRules, listRequests, type FileRequest } from '@/lib/platform'
import { useAuthStore } from '@/stores/auth-store'
import { useBriefTitle } from '@/hooks/use-brief-title'
import { BriefInput } from './brief-input'
import { DropZone } from './drop-zone'
import { LinkCard } from './link-card'
import styles from './autoreview-setup.module.css'

type Step = 'welcome' | 'brand' | 'brief' | 'share'

export function AutoReviewSetup() {
  const { user, setUser } = useAuthStore()
  const router = useRouter()
  const { mutate } = useSWRConfig()
  const { data: projects, error: loadError, mutate: reloadProjects } = useSWR<Project[]>('/projects', () => api.get<Project[]>('/projects'))
  const saved = setupProgress(user)
  const [step, setStep] = React.useState<Step>(saved && saved.step !== 'done' ? saved.step : 'welcome')
  const [projectId, setProjectId] = React.useState(saved?.projectId || '')
  const [brandName, setBrandName] = React.useState('')
  const [guide, setGuide] = React.useState<File | null>(null)
  const [guideText, setGuideText] = React.useState('')
  const [guideRead, setGuideRead] = React.useState(false)
  const [title, setTitle] = React.useState('')
  const [brief, setBrief] = React.useState<File | null>(null)
  const [briefText, setBriefText] = React.useState('')
  const briefTitle = useBriefTitle(brief, briefText, setTitle)
  const [created, setCreated] = React.useState<FileRequest | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState('')
  const [notice, setNotice] = React.useState('')
  const lock = React.useRef(false)
  const heading = React.useRef<HTMLHeadingElement>(null)
  const identity = React.useRef<{ fingerprint: string; key: string } | null>(null)
  const brands = React.useMemo(() => (projects || []).filter(p => ownsProject(user, p)), [projects, user])
  const brand = brands.find(p => p.id === projectId) || brands[0]
  const rulesId = brand?.id || projectId
  const { data: rules, error: rulesError, mutate: reloadRules } = useSWR(step === 'brand' && rulesId ? `/insights/rules?${rulesId}` : null, () => getRules(rulesId), { shouldRetryOnError: false })
  const { data: resumed, error: resumeError, mutate: reloadRequests } = useSWR(step === 'share' && !created ? '/requests' : null, listRequests)
  const delivery = created || resumed?.find(r => r.id === saved?.requestId)
  const activeCount = rules?.rules.filter(r => r.scope === 'brand' && r.active).length || 0

  React.useEffect(() => { heading.current?.focus() }, [step])
  React.useEffect(() => {
    if (projects && projectId && !brands.some(p => p.id === projectId)) {
      setProjectId('')
      setStep('brand')
      setNotice('Your previous brand is no longer available. Choose or create a brand to continue.')
    }
  }, [projects, brands, projectId])

  async function run(action: () => Promise<void>) {
    if (lock.current) return
    lock.current = true; setBusy(true); setError(''); setNotice('')
    try { await action() }
    catch (e) { setError(e instanceof Error ? e.message : 'That did not save. Please try again.') }
    finally { lock.current = false; setBusy(false) }
  }
  async function save(progress: Omit<SetupProgress, 'version'>) {
    const updated = await api.patch<User>('/auth/me/preferences', { autoreview_setup: { version: 1, ...progress } })
    setUser(updated)
  }
  async function ensureBrand() {
    // Re-read before creating: a previous response may have been lost after the server saved it.
    const fresh = await reloadProjects()
    if (!fresh) throw new Error('Could not load your brands. Please try again.')
    const owned = fresh.filter(p => ownsProject(user, p))
    if (projectId && !owned.some(p => p.id === projectId)) throw new Error('This brand is no longer available. Go back to Brand kit and choose your brand again.')
    const existing = owned.find(p => p.id === projectId) || owned[0]
    if (existing) { setProjectId(existing.id); return existing.id }
    if (!brandName.trim()) throw new Error('Give your brand a name first.')
    const result = await api.post<Project>('/projects', { name: brandName.trim(), project_type: 'team', is_workspace: true })
    setProjectId(result.id)
    await reloadProjects([...fresh, result], { revalidate: false })
    return result.id
  }
  async function continueToBrief() {
    const id = await ensureBrand()
    await save({ step: 'brief', projectId: id })
    setStep('brief')
  }
  async function readGuide() {
    const payload = guide ? await briefingFilePayload(guide) : { text: guideText.trim() }
    if (!payload.pdf_base64 && !payload.text) throw new Error('Drop a guide or paste your brand guidelines first.')
    if (payload.text && payload.text.length > 12000) throw new Error('Paste up to 12,000 characters of guidelines, or upload a PDF.')
    const id = await ensureBrand()
    await save({ step: 'brand', projectId: id })
    const result = await importRules({ project_id: id, ...payload })
    setGuideRead(true)
    await reloadRules(await getRules(id), { revalidate: false })
    setNotice(result.drafted ? 'Review the suggestions below. Only rules you approve will be used.' : 'No new rules found. You can add a specific note or continue.')
  }
  async function decide(id: string, action: 'accept' | 'dismiss') {
    const result = await decideSuggestion({ project_id: rulesId, suggestion_id: id, action })
    if (!result.ok) throw new Error('The rule could not be saved. Try again.')
    await reloadRules()
  }
  async function makeLink() {
    if (!title.trim()) throw new Error('Name your first project.')
    if (!brief && !briefText.trim()) throw new Error('Add a brief, a document link, or a short note for your editor.')
    const file = brief ? await briefingFilePayload(brief) : {}
    const id = await ensureBrand()
    const text = briefText.trim()
    const isUrl = /^https?:\/\//i.test(text)
    const payload = { project_id: id, title: title.trim(), receive_iterations: false,
      brief_text: [file.text, isUrl ? '' : text].filter(Boolean).join('\n\n'), brief_url: isUrl ? text : '', brief_pdf_base64: file.pdf_base64 || '' }
    const fingerprint = JSON.stringify(payload)
    if (identity.current?.fingerprint !== fingerprint) identity.current = { fingerprint, key: crypto.randomUUID() }
    const result = await createRequest({ ...payload, idempotency_key: identity.current.key })
    // Show the real link even if saving the resumable UI preference subsequently fails.
    setCreated(result); setStep('share')
    await mutate('/requests', (old: FileRequest[] | undefined) => [result, ...(old || []).filter(r => r.id !== result.id)], { revalidate: false })
    await save({ step: 'share', projectId: id, requestId: result.id })
  }
  async function finish() {
    await save({ step: 'done', projectId: delivery?.project_id || rulesId || undefined, requestId: delivery?.id })
    router.replace('/home')
  }
  function move(next: Step) { setError(''); setNotice(''); setStep(next) }

  if (loadError) return <div className={styles.shell}><div role="alert" className={styles.card}>Could not load your brands. <button className={styles.secondary} onClick={() => void reloadProjects()}>Try again</button></div></div>
  if (!user || !projects) return <div className={styles.shell}><p role="status">Opening AutoReview…</p></div>
  if (!canSetUpAutoReview(user, projects)) return <div className={styles.shell}><div className={styles.card}><h1>Your editing workspace</h1><p>Brand setup is managed by your workspace owner.</p><a href="/home" className={styles.primary}>Open workspace <ArrowRight size={18} /></a></div></div>

  const titles: Record<Step, string> = { welcome: 'A second pair of eyes.\nFor every cut.', brand: 'Make it your brand.', brief: 'Let’s brief your first ad.', share: 'Your editor can take it from here.' }
  return <div className={styles.shell}>
    <div className={styles.wrap}>
      <header className={styles.header}><span className={styles.wordmark}><Image src="/autoreview-icon.png" alt="" width={28} height={28} /> AutoReview</span><span className={styles.counter}>{step === 'welcome' ? 'Your first review starts here' : `${['brand', 'brief', 'share'].indexOf(step) + 1} of 3`}</span></header>
      {step !== 'welcome' && <nav className={styles.progress} aria-label="Setup progress">{['Brand', 'Briefing', 'Share'].map((label, i) => <span key={label} data-active={i <= ['brand', 'brief', 'share'].indexOf(step)} aria-current={i === ['brand', 'brief', 'share'].indexOf(step) ? 'step' : undefined}>{label}</span>)}</nav>}
      <section className={styles.card} key={step}>
        {step === 'welcome' && <div className={styles.scene} aria-hidden="true"><span className={styles.paper}><FileText size={34} /><small>BRIEF</small></span><span className={styles.connector} /><span className={styles.scan}><ScanLine size={46} /><i /></span><span className={styles.connector} /><span className={styles.ready}><Check size={34} /><small>DELIVERY</small></span></div>}
        {step !== 'brief' && <div className={styles.kicker}>{step === 'welcome' ? 'Less back-and-forth. More done.' : step === 'brand' ? 'Your brand, your rules' : 'Briefing saved · Waiting for files'}</div>}
        <h1 ref={heading} tabIndex={-1} className={styles.title}>{titles[step]}</h1>
        {step !== 'brief' && <p className={styles.description}>{step === 'welcome' ? 'Aditor’s editing best practices, with your brief and brand rules on top.' : step === 'brand' ? 'Got a brand guide or a few non-negotiables? Drop them here. No kit? Skip it.' : 'Send this upload link to your editor. Their delivery and review will appear in your dashboard.'}</p>}

        {step === 'welcome' && <><div className={styles.capabilities}><span><BookOpen size={18} /> Your brand rules</span><span><Sparkles size={18} /> Ad best practices</span><span><Link2 size={18} /> One editor link</span></div><button className={styles.primary} onClick={() => move('brand')}>Get started <ArrowRight size={18} /></button></>}

        {step === 'brand' && <div className={styles.form}>
          {brands.length === 1 ? <div className={styles.label}>Brand<div className={styles.brandIdentity}><span>{brand.name}</span><Check size={16} aria-hidden="true" /></div></div> : brands.length > 1 ? <div className={styles.label}>
            <span id="setup-brand-label">Brand</span>
            <Select.Root value={brand?.id} disabled={busy} onValueChange={id => { setProjectId(id); setGuideRead(false); setNotice('') }}>
              <Select.Trigger aria-labelledby="setup-brand-label" className={`${styles.input} ${styles.brandTrigger}`}><Select.Value /><Select.Icon><ChevronDown size={16} /></Select.Icon></Select.Trigger>
              <Select.Portal><Select.Content position="popper" sideOffset={6} className={`owner-sheet ${styles.brandMenu}`}><Select.Viewport>{brands.map(p => <Select.Item key={p.id} value={p.id} className={styles.brandOption}><Select.ItemText>{p.name}</Select.ItemText><Select.ItemIndicator><Check size={16} /></Select.ItemIndicator></Select.Item>)}</Select.Viewport></Select.Content></Select.Portal>
            </Select.Root>
          </div> : <label className={styles.label}>Brand name<input className={styles.input} value={brandName} onChange={e => setBrandName(e.target.value)} placeholder="e.g. Northline" maxLength={255} disabled={busy} /></label>}

          {guide ? <ChosenFile file={guide} remove={() => { setGuide(null); setGuideRead(false) }} disabled={busy} /> : <DropZone compact accept={BRIEFING_ACCEPT} disabled={busy} title="Drop your brand kit" hint="PDF, Markdown or text · up to 10 MB" onFiles={([f]) => { setGuide(f); setGuideRead(false); setError('') }} />}
          {!guide && <label className={styles.label}>Or paste your guidelines<textarea aria-label="Brand guidelines" className={styles.input} rows={3} value={guideText} disabled={busy} onChange={e => { setGuideText(e.target.value); setGuideRead(false) }} placeholder="Always show our logo on the end card…" /></label>}
          {(guide || guideText.trim()) && !guideRead && <button className={styles.primary} disabled={busy} onClick={() => void run(readGuide)}>{busy ? 'Reading your guide…' : 'Read my brand kit'} <ArrowRight size={18} /></button>}
          {notice && <p role="status" className={styles.note}>{notice}</p>}
          {rulesError && <div role="alert" className={styles.note}>Could not load your rules. <button className={styles.textButton} onClick={() => void reloadRules()}>Try again</button></div>}
          {!!rules?.suggestions.length && <div className={styles.suggestions}><h2>For your approval</h2><p className={styles.note}>Suggestions stay inactive until you choose “Use rule”.</p>{rules.suggestions.map(s => <article key={s.id}><strong>{s.name || 'Suggested rule'}</strong><p>{s.what}</p><div><button disabled={busy} className={styles.textButton} onClick={() => void run(() => decide(s.id, 'dismiss'))}>Dismiss</button><button disabled={busy} className={styles.ruleButton} aria-label={`Use rule: ${s.name || 'Suggested rule'}`} onClick={() => void run(() => decide(s.id, 'accept'))}><Check size={16} /> Use rule</button></div></article>)}</div>}
          {activeCount > 0 && <p className={styles.note}><Check size={16} /> {activeCount} active brand {activeCount === 1 ? 'rule' : 'rules'} saved.</p>}
          {(guideRead || activeCount > 0 || !!rules?.suggestions.length) && <button className={styles.primary} disabled={busy} onClick={() => void run(continueToBrief)}>Continue to briefing <ArrowRight size={18} /></button>}
          <button className={styles.secondary} disabled={busy} onClick={() => void run(continueToBrief)}>{guideRead || activeCount ? 'Add more rules later' : 'Skip brand kit'}</button>
        </div>}

        {step === 'brief' && <form className={`${styles.form} ${styles.briefForm}`} onSubmit={e => { e.preventDefault(); void run(makeLink) }}>
          <label className={styles.label}>Project name<input className={styles.input} value={title} onChange={e => { briefTitle.edit(); setTitle(e.target.value) }} maxLength={255} required disabled={busy} /></label>
          <BriefInput file={brief} onFile={setBrief} text={briefText} onText={setBriefText} disabled={busy} />
          <button type="submit" className={styles.primary} disabled={busy || !title.trim() || (!brief && !briefText.trim())}>{busy ? 'Creating your link…' : 'Create upload link'} <ArrowRight size={18} /></button>
          <button type="button" className={styles.secondary} disabled={busy} onClick={() => move('brand')}><ArrowLeft size={16} /> Brand kit</button>
        </form>}

        {step === 'share' && (delivery ? <div className={styles.form}>
          <div className={styles.delivery}><FileText size={22} /><span><strong>{delivery.title}</strong><small>Waiting for files</small></span><Check size={20} /></div>
          <LinkCard url={delivery.url} label="Your editor’s upload link" hint="Tap to copy. Your editor won’t need an account." copiedHint="Copied. Send it to your editor — you’re set." openLabel="Upload an ad yourself" />
          <button className={styles.primary} disabled={busy} onClick={() => void run(finish)}>{busy ? 'Saving…' : 'Open dashboard'} <ArrowRight size={18} /></button>
        </div> : <div className={styles.form}>{resumeError ? <p role="alert">Could not load your saved link. <button className={styles.secondary} onClick={() => void reloadRequests()}>Try again</button></p> : !resumed ? <p role="status">Loading your saved link…</p> : <><p>Your saved request is no longer available.</p><button className={styles.primary} onClick={() => move('brief')}>Create a new briefing</button></>}</div>)}
        {error && <p role="alert" className={styles.error}>{error}</p>}
      </section>
      {step !== 'share' && <footer className={styles.footer}><button disabled={busy} className={styles.textButton} onClick={() => void run(finish)}>Finish setup later</button><span>Pick this up again from your dashboard.</span></footer>}
    </div>
  </div>
}

function ChosenFile({ file, remove, disabled }: { file: File; remove: () => void; disabled: boolean }) {
  return <div className={styles.file}><FileText size={22} /><span>{file.name}</span><button type="button" disabled={disabled} aria-label={`Remove ${file.name}`} onClick={remove}><X size={18} /></button></div>
}
