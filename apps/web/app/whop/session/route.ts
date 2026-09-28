import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'
const headers = { 'Cache-Control': 'no-store' }
const errors: Record<number, string> = {
  401: 'Open Autoreview inside Whop to sign in. If it is already open there, close the app and open it again.',
  403: 'Your Whop membership does not currently include access to this workspace. Check your access in Whop or contact support.',
  409: 'An account already exists for this identity. Contact support to connect it to Whop.',
  429: 'Too many sign-in attempts. Wait a minute, then try again.',
  503: 'We could not check your Whop access right now. Please try again shortly.',
}

export async function POST(request: Request) {
  const token = request.headers.get('x-whop-user-token')
  if (!token || token.length > 16384) {
    return NextResponse.json({ detail: errors[401] }, { status: 401, headers })
  }
  try {
    // Server-only URL: Whop adds its identity header to this same-origin request.
    // No cookies, caller-chosen destination or Suite credentials are forwarded.
    const publicBase = process.env.NEXT_PUBLIC_API_URL
    const base = process.env.API_INTERNAL_URL || (publicBase?.startsWith('http') ? publicBase : 'http://localhost:8000')
    const response = await fetch(`${base.replace(/\/$/, '')}/auth/whop`, {
      method: 'POST', headers: { 'x-whop-user-token': token },
      cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(25000),
    })
    if (!response.ok) {
      const status = errors[response.status] ? response.status : 503
      return NextResponse.json({ detail: errors[status] }, { status, headers })
    }
    const data = await response.json()
    if (typeof data.access_token !== 'string' || typeof data.refresh_token !== 'string') throw new Error('Incomplete session')
    return NextResponse.json({ access_token: data.access_token, refresh_token: data.refresh_token }, { headers })
  } catch {
    return NextResponse.json({ detail: errors[503] }, { status: 503, headers })
  }
}
