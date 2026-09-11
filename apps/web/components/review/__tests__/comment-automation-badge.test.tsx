/**
 * An automation commenting through a share link is a guest, so it wore the "Client" badge - its
 * notes read on a client-facing timeline as though the client had written them.
 *
 * Saskia, 2026-09-11, looking at Auto Review's comments in FreeFrame: they are labelled Client.
 * Aditor's reviewer posts this way by design (no account, share token only), and mislabelling a
 * machine as the customer is the kind of confusion nobody untangles later.
 */
import { render, screen } from '@testing-library/react'
import { describe, it, expect, beforeAll } from 'vitest'

const AUTOMATION = 'review@aditor.ai'

describe('the Automated badge', () => {
  beforeAll(() => {
    process.env.NEXT_PUBLIC_AUTOMATION_GUEST_EMAILS = AUTOMATION
  })

  const comment = (email: string, name: string) => ({
    id: 'c1',
    body: 'No clear CTA in the final ten seconds.',
    author_id: null,
    guest_author_id: 'g1',
    guest_author: { id: 'g1', name, email },
    created_at: new Date().toISOString(),
    resolved: false,
    replies: [],
  })

  it('is documented as matching on the EMAIL, never the typed name', () => {
    // The name beside a guest comment is whatever was typed into the comment prompt, so a person
    // could otherwise call themselves Auto Review and inherit the badge.
    const src = require('node:fs').readFileSync(
      'components/review/comment-panel.tsx', 'utf8'
    ) as string
    expect(src).toMatch(/guest_author\?\.email/)
    expect(src).toMatch(/matched on the guest's EMAIL/)
  })

  it('leaves an instance that configures no automation exactly as it was', () => {
    const src = require('node:fs').readFileSync(
      'components/review/comment-panel.tsx', 'utf8'
    ) as string
    // Empty by default - the Set is built from an env var that is unset upstream.
    expect(src).toMatch(/NEXT_PUBLIC_AUTOMATION_GUEST_EMAILS \|\| ''/)
    expect(src).toMatch(/isGuestAuthor && !isAutomation/)   // real guests keep "Client"
  })
})
