/**
 * A folder IS the hand-in now, so the Trello card link has to arrive with it.
 *
 * Requiring the link on the server while giving nobody a box to type it into does not enforce
 * anything - it stops people creating folders. The box and the requirement ship together, and
 * both are off unless an instance turns them on.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'

const dialog = readFileSync('components/projects/name-dialog.tsx', 'utf8')
const page = readFileSync('app/(dashboard)/projects/[id]/page.tsx', 'utf8')
const hook = readFileSync('hooks/use-folders.ts', 'utf8')

describe('the card link on a new folder', () => {
  it('is a second field the dialog only grows when asked', () => {
    expect(dialog).toContain('extraField?:')
    // Every other caller passes nothing and keeps the single-field dialog it has always had.
    expect(dialog).toContain('onSubmit(trimmed, extraField ? extra.trim() : undefined)')
  })

  it('cannot be submitted empty when it is required', () => {
    expect(dialog).toContain('const extraMissing = !!extraField?.required && !extra.trim()')
    expect(dialog).toContain('disabled={!value.trim() || extraMissing}')
  })

  it('only appears where an instance named it', () => {
    expect(page).toContain('NEXT_PUBLIC_FOLDER_LINK_LABEL')
    expect(page).toContain('FOLDER_LINK_LABEL\n            ? {')
  })

  it('is sent on to the api as the folder description', () => {
    expect(hook).toContain('...(description ? { description } : {})')
  })
})
