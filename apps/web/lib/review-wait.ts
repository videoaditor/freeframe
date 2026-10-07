import type { ReviewProgress, ReviewTimeRange } from './platform'
const valid = (r?: {lowerSeconds:number;upperSeconds:number;sampleCount:number} | null) => !!r && [r.lowerSeconds,r.upperSeconds,r.sampleCount].every(Number.isFinite) && r.lowerSeconds >= 0 && r.upperSeconds > 0 && r.upperSeconds >= r.lowerSeconds
const span = (r: {lowerSeconds:number;upperSeconds:number}) => `${r.lowerSeconds/60}${r.lowerSeconds===r.upperSeconds?'':`–${r.upperSeconds/60}`} min`
export function serverElapsed(p?: ReviewProgress | null): number | undefined {
  if (p?.elapsedSeconds !== undefined) return Number.isFinite(p.elapsedSeconds) && p.elapsedSeconds >= 0 ? p.elapsedSeconds : undefined
  const t=p?.timing
  if (t?.schema_version==='autoreview.timing.v1' && Number.isFinite(t.started_at) && Number.isFinite(t.server_now)) return Math.max(0,(t.server_now!-t.started_at!)/1000)
  if (p?.startedAgoSeconds !== undefined && Number.isFinite(p.startedAgoSeconds) && p.startedAgoSeconds >= 0) return p.startedAgoSeconds
}
export function waitExpectation(p?: ReviewProgress | null) {
 const t=p?.timing?.schema_version==='autoreview.timing.v1'?p.timing:undefined
 const scoped=(r:ReviewTimeRange|undefined,scope:ReviewTimeRange['scope'],n:number)=>valid(r)&&r?.scope===scope&&r.sampleCount>=n?r:undefined
 const total=t?.calibration==='measured'?scoped(t.total,'submission-to-publication',30):undefined
 const remaining=total?scoped(t?.remaining,'phase-conditioned-remaining',30):undefined
 if(remaining) return {label:`About ${span(remaining)} remaining`,detail:'Measured from similar reviews still in this phase. Updated when status is checked.',upper:total!.upperSeconds,scope:'total'}
 if(total) return {label:`Feedback usually ${span(total)} after upload`,detail:`Based on ${total.sampleCount} matching completed reviews, including preparation, queue and feedback publication.`,upper:total.upperSeconds,scope:'total'}
 const analysis=t?scoped(t.analysis,'analysis',5):valid(p?.estimate)&&p!.estimate!.sampleCount>=5?p!.estimate!:undefined
 if(analysis) return {label:`Analysis usually ${span(analysis)}`,detail:`Based on ${analysis.sampleCount} recent similar videos. Preparation, queue time and feedback publication are additional.`,upper:analysis.upperSeconds,scope:'analysis'}
 return {label:'Measuring typical wait time',detail:'Not enough matching reviews to give a reliable time range yet. Feedback appears automatically.',scope:'calibrating'}
}
