import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

// A var() pointing at a custom property nobody defines is not ignored: it makes the
// whole declaration invalid at computed-value time, so the property resolves to its
// initial or inherited value instead. `--font-sans: var(--font-geist), system-ui, ...`
// therefore produced no font-family at all rather than system-ui, and every page
// rendered in the browser's default serif on any build where next/font's class was
// missing from <body>. The fallback silently was not one.
describe('globals.css custom properties', () => {
  const raw = readFileSync(join(__dirname, '..', 'globals.css'), 'utf8')
  // Strip comments first, or prose describing a bad declaration reads as one.
  const css = raw.replace(/\/\*[\s\S]*?\*\//g, '')

  function matches(pattern: RegExp): string[] {
    const found: string[] = []
    let m: RegExpExecArray | null
    while ((m = pattern.exec(css)) !== null) found.push(m[1])
    return found
  }

  it('references no custom property it never defines', () => {
    const defined = matches(/(--[a-z0-9-]+)\s*:/gi)
    const referenced = matches(/var\(\s*(--[a-z0-9-]+)/gi)
    // next/font sets --font-sans on <body> at runtime, but globals.css gives it a
    // static value too, so it counts as defined here. Anything genuinely absent is
    // a dangling reference that kills the whole declaration around it.
    const dangling = referenced.filter(
      (name, i) => referenced.indexOf(name) === i && defined.indexOf(name) === -1,
    )
    expect(dangling).toEqual([])
  })

  it('gives --font-sans a fallback that stands on its own', () => {
    const decl = css.match(/--font-sans:\s*([^;]+);/)
    expect(decl).not.toBeNull()
    expect(decl![1]).not.toContain('var(')
    expect(decl![1]).toMatch(/sans-serif\s*$/)
  })
})
