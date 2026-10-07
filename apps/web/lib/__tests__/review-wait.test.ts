import { expect, it } from 'vitest'
import { waitExpectation, serverElapsed } from '../review-wait'

it('keeps analysis separate and hides total/rest without calibrated timing',()=>{
 expect(waitExpectation({stage:'reading'}).label).toBe('Measuring typical wait time')
 expect(waitExpectation({stage:'reading',estimate:{lowerSeconds:90,upperSeconds:180,sampleCount:5}})).toMatchObject({label:'Analysis usually 1.5–3 min'})
 expect(waitExpectation({stage:'reading',estimate:{lowerSeconds:-1,upperSeconds:2,sampleCount:5}}).label).toBe('Measuring typical wait time')
})
it('uses calibrated scope; remaining must come from a conditional server range',()=>{
 const timing={schema_version:'autoreview.timing.v1' as const,calibration:'measured' as const,total:{lowerSeconds:180,upperSeconds:300,sampleCount:30,scope:'submission-to-publication' as const}}
 expect(waitExpectation({stage:'reading',timing}).label).toBe('Feedback usually 3–5 min after upload')
 expect(waitExpectation({stage:'reading',timing:{...timing,remaining:{lowerSeconds:30,upperSeconds:60,sampleCount:30,scope:'phase-conditioned-remaining'}}}).label).toBe('About 0.5–1 min remaining')
})
it('uses server elapsed, including queue, and does not start an unconfirmed clock',()=>{
 expect(serverElapsed({stage:'reading',elapsedSeconds:243,startedAgoSeconds:20})).toBe(243)
 expect(serverElapsed({stage:'reading',timing:{schema_version:'autoreview.timing.v1',calibration:'collecting',started_at:1000,server_now:241000}})).toBe(240)
 expect(serverElapsed({stage:'waiting'})).toBeUndefined()
 expect(serverElapsed({stage:'waiting',elapsedSeconds:NaN})).toBeUndefined()
})
