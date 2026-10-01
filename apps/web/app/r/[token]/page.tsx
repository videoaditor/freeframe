'use client'

import * as React from 'react'
import useSWR from 'swr'
import { ArrowLeft } from 'lucide-react'
import { finishRequest, objectToNote, requestReview, uploadToRequest, viewRequest, type RequestAsset } from '@/lib/platform'
import { DropZone } from '@/components/v2/drop-zone'
import { UploadCard, type UploadPhase } from '@/components/v2/upload-card'
import { RequestWorkspace, SubmissionSuccess } from '@/components/v2/request-workspace'

interface Who { name: string; email: string }
interface Job { id: string; file: File; progress: number; phase: UploadPhase; error?: string; assetId?: string }
const WHO_KEY = 'aditor-request-who'
const validWho = (who: Who) => !!who.name.trim() && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(who.email)

export default function RequestPage({ params: { token } }: { params: { token: string } }) {
  const { data: view, error: viewError, mutate: refreshView } = useSWR(`/r/${token}`, () => viewRequest(token), { shouldRetryOnError: false, refreshInterval: d => d?.completed_at ? 0 : 60000 })
  const { data: review, error: reviewError, mutate: refreshReview } = useSWR(view?.assets.length ? `/r/${token}/review` : null, () => requestReview(token), { refreshInterval: d => d?.completed_at || view?.completed_at ? 0 : 10000 })
  const [jobs, setJobs] = React.useState<Job[]>([])
  const [who, setWho] = React.useState<Who>({ name: '', email: '' })
  const identity = React.useRef<Who | null>(null)
  const identityWaiters = React.useRef<((who: Who) => void)[]>([])
  const [error, setError] = React.useState('')
  const [waitingIdentity, setWaitingIdentity] = React.useState(false)
  const [revision, setRevision] = React.useState<RequestAsset | null>(null)
  const [uploadMode, setUploadMode] = React.useState(false)
  const [activeId, setActiveId] = React.useState<string>()
  const [completedAt, setCompletedAt] = React.useState<string>()
  const finishAttempt = React.useRef('')
  React.useEffect(() => {
    try { const saved = JSON.parse(localStorage.getItem(WHO_KEY) || 'null'); if (saved && validWho(saved)) { setWho(saved); identity.current = saved } } catch { /* private browsing */ }
  }, [])
  const refresh = React.useCallback(async () => { await Promise.allSettled([refreshView(), refreshReview()]) }, [refreshView, refreshReview])
  const uploading = jobs.some(j => j.phase === 'uploading')
  const complete = !!(view?.completed_at || review?.completed_at || completedAt)
  const assets = review?.assets || []
  const hasSubmission = (view?.assets.length || 0) > 0
  const showUpload = !complete && (uploadMode || uploading || jobs.some(j => j.phase === 'error') || (!hasSubmission && !jobs.some(j => j.phase === 'done')))
  React.useEffect(() => { window.scrollTo?.({ top: 0 }) }, [showUpload, complete])
  const readyToFinish = !!review?.assets.length && review.assets.every(a => a.processing === 'ready' && a.review_state === 'clear') && review.gate.status === 'clear'
  React.useEffect(() => {
    if (!readyToFinish || uploading || complete || jobs.some(j => j.phase === 'error')) return
    const signature = review!.assets.map(a => a.version_id).join(',')
    if (finishAttempt.current === signature) return
    finishAttempt.current = signature
    finishRequest(token).then(r => { setCompletedAt(r.completed_at); refresh() }).catch(e => setError(e.message))
  }, [readyToFinish, uploading, complete, jobs, review, token, refresh])

  const update = (id: string, patch: Partial<Job>) => setJobs(js => js.map(j => j.id === id ? { ...j, ...patch } : j))
  const submitIdentity = (e: React.FormEvent) => {
    e.preventDefault()
    if (!validWho(who)) { setError('Add your name and a valid email to submit.'); return }
    const value = { name: who.name.trim(), email: who.email.trim() }
    identity.current = value
    try { localStorage.setItem(WHO_KEY, JSON.stringify(value)) } catch { /* private browsing */ }
    identityWaiters.current.splice(0).forEach(resolve => resolve(value)); setWaitingIdentity(false); setError('')
  }
  const upload = async (job: Job) => {
    update(job.id, { phase: 'uploading', progress: 0, error: undefined }); setError('')
    try {
      const result = await uploadToRequest(token, identity.current || { name: '', email: '' }, job.file, progress => update(job.id, { progress }), { assetId: job.assetId, identity: async () => {
        if (identity.current) return identity.current
        setWaitingIdentity(true)
        return new Promise<Who>(resolve => identityWaiters.current.push(resolve))
      } })
      update(job.id, { phase: 'done', progress: 1, assetId: result.asset_id })
      setActiveId(result.asset_id); setUploadMode(false); setRevision(null); refresh()
    } catch (e) { update(job.id, { phase: 'error', error: e instanceof Error ? e.message : 'Upload stopped. Try again.' }) }
  }
  const onFiles = async (files: File[]) => {
    if (complete) return
    if (files.some(file => !file.type.startsWith('video/') && !/\.(mp4|mov|webm|m4v)$/i.test(file.name))) { setError('Choose a video file for this review.'); return }
    const chosen = revision ? files.slice(0, 1) : files
    const fresh = chosen.map(file => ({ id: crypto.randomUUID(), file, assetId: revision?.asset_id, progress: 0, phase: 'uploading' as UploadPhase }))
    setJobs(js => [...js, ...fresh])
    for (const job of fresh) await upload(job)
  }
  const uploaderDetails = identity.current ? <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-sm text-text-secondary"><span>Submitting as {who.name} · {who.email}</span><button className="min-h-11 text-accent" onClick={() => { identity.current = null; setWho(w => ({ ...w })) }}>Edit details</button></div> : <form onSubmit={submitIdentity} className="mt-6">
    <div className="grid gap-4 sm:grid-cols-2">{(['name', 'email'] as const).map(field => <label key={field} className="text-xs font-medium text-text-secondary">Your {field}<input required type={field === 'email' ? 'email' : 'text'} value={who[field]} autoComplete={field} onChange={e => { setWho(w => ({ ...w, [field]: e.target.value })); identity.current = null }} className="field mt-2 min-h-11 w-full" /></label>)}</div>
    <div className="mt-3 flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-text-tertiary">{waitingIdentity ? 'Transfer complete. Add your details to submit.' : 'Your files can upload while you fill this in.'}</p>{!identity.current && <button className="min-h-11 rounded-full bg-accent px-5 text-sm font-semibold text-white">{uploading ? 'Submit my files' : 'Save details'}</button>}</div>

  </form>
  const jobCard = (job: Job) => <div key={job.id} className="mt-3"><UploadCard file={job.file} name={job.file.name} size={job.file.size} phase={job.phase} progress={job.progress} error={job.error} onRetry={() => upload(job)} onRemove={job.phase === 'error' ? () => setJobs(js => js.filter(j => j.id !== job.id)) : undefined} />{job.progress === 1 && job.phase === 'uploading' && <p className="mt-2 text-xs text-text-secondary">{waitingIdentity ? 'Uploaded · waiting for your details' : 'Submitting your file…'}</p>}</div>
  return <div className="owner-workspace min-h-screen bg-bg-primary text-text-primary">
    <header className={`relative mx-auto flex h-20 max-w-[1120px] items-center border-b border-border px-5 sm:px-8 ${complete ? 'justify-center' : 'justify-between'}`}>{view?.logo_url ? /* eslint-disable-next-line @next/next/no-img-element */ <img src={view.logo_url} alt={view.brand} className="h-8 max-w-40 object-contain" /> : <span className="text-lg font-semibold tracking-tight">{view?.brand || 'File request'}</span>}<span className={`text-xs text-text-tertiary ${complete ? 'absolute right-5 sm:right-8' : ''}`}>{complete ? 'Completed' : showUpload ? 'Editor upload' : 'Editor review'}</span></header>
    <main className={`mx-auto px-5 pb-16 pt-8 sm:px-8 sm:pt-10 ${showUpload ? 'max-w-3xl' : 'max-w-[1120px]'}`}>
      {viewError && (!view || [401, 403, 404, 410].includes(viewError.status)) ? <div className="py-20 text-center"><h1 className="text-2xl font-semibold">{viewError.status === 410 ? 'This link is closed' : 'This link could not be opened'}</h1><p className="mt-3 text-text-secondary">{viewError.message}</p></div> : !view ? <p role="status">Opening your project…</p> : <>
      <div className={`mb-7 ${complete ? 'text-center' : ''}`}><p className="mb-2 text-xs font-medium uppercase tracking-[0.12em] text-text-tertiary">{revision && showUpload ? `Next version · v${revision.version + 1}` : complete ? 'Handed in. Nicely done.' : 'Your project'}</p><h1 className="text-balance text-3xl font-semibold tracking-tight">{view.title}</h1></div>
      {error && <div role="alert" className="mb-5 rounded-xl border border-border p-4 text-sm text-status-error">{error}{readyToFinish && !complete && <button className="ml-3 min-h-11 underline" onClick={() => { finishAttempt.current = ''; refresh() }}>Try again</button>}</div>}
      {complete ? <SubmissionSuccess token={token} brand={view.brand} /> : <>
      {showUpload ? <>
        {hasSubmission && !uploading && <button className="mb-4 flex min-h-11 items-center gap-2 text-sm text-text-secondary" onClick={() => { setUploadMode(false); setRevision(null) }}><ArrowLeft size={16} /> Back to {revision ? `v${revision.version} ` : ''}feedback</button>}
        <DropZone onFiles={onFiles} multiple={!revision} accept="video/*" disabled={uploading} title={revision ? `Drop ${revision.name} · v${revision.version + 1}` : 'Drop your files to begin'} hint={revision ? 'New filename? No problem. This replaces the selected cut.' : 'Video files · or choose files'} />{jobs.filter(j => j.phase !== 'done').map(jobCard)}{uploaderDetails}
      </> : <>
        <RequestWorkspace token={token} brand={view.brand} assets={assets} activeId={activeId} onSelect={setActiveId} onRefresh={refresh} onRevise={asset => { setRevision(asset); setUploadMode(true) }} onObject={async (asset, comment, text) => { const result = await objectToNote(token, { asset_id: asset.asset_id, version_id: asset.version_id, comment_id: comment.id, body: comment.body, text, name: who.name }); refresh(); return result }} />
        {reviewError && <p role="alert" className="mb-5 text-sm text-status-error">Feedback is temporarily unavailable. Your files are safe. <button onClick={refresh} className="min-h-11 underline">Try again</button></p>}

      </>}
      </>}
      </>}
    </main>
  </div>
}
