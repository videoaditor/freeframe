import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'
const reply = (title: string | null, status = 200) => NextResponse.json({ title }, { status, headers: { 'Cache-Control': 'no-store' } })

/** Best-effort public Google Docs title. Never fetch an arbitrary caller-selected host. */
export async function POST(request: Request) {
  const token = request.headers.get('x-freeframe-token') || request.headers.get('authorization')?.replace(/^Bearer /i, '')
  if (!token || token.length > 16384) return reply(null, 401)
  try {
    const body = await request.text()
    if (body.length > 4096) return reply(null, 400)
    const url = new URL(JSON.parse(body).url)
    const match = url.pathname.match(/^\/document\/d\/([a-zA-Z0-9_-]{10,200})(?:\/|$)/)
    if (url.protocol !== 'https:' || url.hostname !== 'docs.google.com' || url.port || url.username || url.password || !match) return reply(null)
    const base = process.env.API_INTERNAL_URL || 'http://localhost:8000'
    const auth = await fetch(`${base.replace(/\/$/, '')}/auth/me`, { headers: { Authorization: `Bearer ${token}` }, redirect: 'error', cache: 'no-store', signal: AbortSignal.timeout(4000) })
    if (!auth.ok) return reply(null, auth.status === 401 || auth.status === 403 ? auth.status : 503)
    const response = await fetch(`https://docs.google.com/document/d/${match[1]}/edit`, { redirect: 'error', cache: 'no-store', signal: AbortSignal.timeout(5000) })
    if (!response.ok || !response.headers.get('content-type')?.includes('text/html') || !response.body) return reply(null)
    const reader = response.body.getReader(), decoder = new TextDecoder()
    let html = '', size = 0
    try {
      while (size < 512 * 1024) {
        const { done, value } = await reader.read()
        if (done) break
        size += value.byteLength
        if (size > 512 * 1024) return reply(null)
        html += decoder.decode(value, { stream: true })
        if (/<\/title>/i.test(html)) break
      }
    } finally { await reader.cancel() }
    const raw = html.match(/<title[^>]*>([^]*?)<\/title>/i)?.[1]
    if (!raw || !/ - Google Docs\s*$/.test(raw)) return reply(null)
    const title = raw.replace(/ - Google Docs\s*$/, '').replace(/&#(x[0-9a-f]+|\d+);|&(amp|quot|apos|lt|gt);/gi, (_, n, named) => {
      if (n) { const code = n[0].toLowerCase() === 'x' ? parseInt(n.slice(1), 16) : Number(n); return code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : '' }
      return ({ amp: '&', quot: '"', apos: "'", lt: '<', gt: '>' } as Record<string, string>)[named.toLowerCase()]
    }).trim().slice(0, 255)
    return reply(title && !/^(sign in|page not found|access denied|google docs)$/i.test(title) ? title : null)
  } catch { return reply(null) }
}
