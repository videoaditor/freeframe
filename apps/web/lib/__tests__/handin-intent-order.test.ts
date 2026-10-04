import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

// Sandra, 2026-10-04: an upload through the hand-in page failed, she re-uploaded straight into the folder, and
// nothing ever marked it as a deliberate hand-in because the intent was only recorded AFTER every upload.
const page = readFileSync('app/(dashboard)/handin/page.tsx', 'utf8')

describe('the hand-in page records the intent to deliver before any upload starts', () => {
  it('calls the deliver endpoint before it starts the first upload', () => {
    const firstDeliver = page.indexOf('/api/gate/deliver')
    const firstUpload = page.indexOf('startUpload(f, projectId')
    expect(firstDeliver).toBeGreaterThan(-1)
    expect(firstUpload).toBeGreaterThan(-1)
    expect(firstDeliver).toBeLessThan(firstUpload)
  })
  it('still asks again after the uploads, for the status it shows', () => {
    const calls = page.split('/api/gate/deliver').length - 1
    expect(calls).toBeGreaterThanOrEqual(2)
    expect(page.lastIndexOf('/api/gate/deliver')).toBeGreaterThan(page.indexOf('startUpload(f, projectId'))
  })
  it('does not let a failing early call stop the hand-in', () => {
    const early = page.slice(page.indexOf('/api/gate/deliver'), page.indexOf('startUpload(f, projectId'))
    expect(early).toContain('.catch(')
  })
})
