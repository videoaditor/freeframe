/**
 * An editor who uploads and sees nothing cannot tell "the review is coming" from "nobody is
 * looking".
 *
 * Saskia, 2026-09-12: "when they upload the videos for the first time, they should somehow get a
 * message that it was sent to review." With the review automatic there is no button they press
 * any more, so this line is what replaces that button - the reassurance, not the action.
 *
 * The notice is a build-time string. Empty means the line does not render at all, which is
 * upstream's behaviour and every self-hoster's: no instance inherits a promise about a reviewer
 * it does not run.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'

const src = readFileSync('components/layout/uploads-panel.tsx', 'utf8')

describe('the upload-complete review notice', () => {
  it('comes from a build-time setting, empty by default', () => {
    expect(src).toContain("process.env.NEXT_PUBLIC_UPLOAD_REVIEW_NOTICE || ''")
  })

  it('renders only when the instance set one', () => {
    // `&& REVIEW_NOTICE` is the whole safeguard: no setting, no sentence.
    expect(src).toContain("upload.status === 'complete' && REVIEW_NOTICE")
  })

  it('says nothing about a verdict', () => {
    // It reports that the review is COMING. A word about passing, failing or a score here would
    // make the upload panel a place where delivery looks conditional, and it never is.
    for (const word of ['approved', 'passed', 'failed', 'score', 'blocked']) {
      expect(src.toLowerCase()).not.toContain(`notice} ${word}`)
    }
    expect(src).not.toContain('REVIEW_VERDICT')
  })
})
