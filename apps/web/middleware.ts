import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// '/' is the public WeTransfer-style front door (platform v2); '/r/' is a file-request link.
const PUBLIC_ROUTES = ['/', '/login', '/setup', '/whop', '/whop/session']
const PUBLIC_PREFIXES = ['/invite/', '/share/', '/r/']

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
// Build-time flag (docker-compose.aditor.yml): only bounce /login straight to the
// central gate on an instance that has actually registered with one - unset/false
// keeps a dev or self-hosted instance showing the password break-glass form instead
// of 307ing into a 404.
const OIDC_ENABLED = process.env.NEXT_PUBLIC_OIDC_ENABLED === 'true'

function isPublicRoute(pathname: string): boolean {
  if (PUBLIC_ROUTES.includes(pathname)) return true
  if (PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix))) return true
  return false
}

function sanitizeFrom(value: string | null): string {
  return value && value.startsWith('/') && !value.startsWith('//') ? value : '/home'
}

async function isSetupDone(request: NextRequest): Promise<boolean> {
  if (request.cookies.get('ff_setup_done')?.value) return true
  try {
    const res = await fetch(`${API_URL}/setup/status`, { next: { revalidate: 60 } })
    if (!res.ok) return false
    const data = await res.json()
    return !data.needs_setup
  } catch {
    // API unreachable - treat setup as not confirmed, fall through to the form.
    return false
  }
}

// /login must never paint the Autoreview shell for a visitor who is about to be sent
// elsewhere: a cold signed-out hit bounces straight to the gate, and a hit that already
// carries a session (the post-gate-callback bounce) bounces straight to its destination.
// Both happen here, server-side, before any HTML renders. page.tsx keeps its own
// client-side checks as a belt-and-suspenders fallback for whatever this misses (e.g.
// an unreachable API on the setup check).
async function handleLoginRoute(request: NextRequest): Promise<NextResponse | null> {
  const { searchParams } = request.nextUrl

  // A gate failure comes back as ?error=... - show it, never loop back into the gate.
  if (searchParams.has('error')) return null

  const accessToken = request.cookies.get('ff_access_token')?.value
  if (accessToken) {
    return NextResponse.redirect(new URL(sanitizeFrom(searchParams.get('from')), request.url), 307)
  }

  if (!OIDC_ENABLED) return null

  const whop = request.cookies.get('ff_auth_provider')?.value === 'whop' || request.headers.has('x-whop-user-token')
  if (whop) return null

  // A refresh-token-only session needs the client to renew it first; don't force a
  // fresh gate sign-in just because the short-lived access cookie already expired.
  if (request.cookies.get('ff_refresh_token')?.value) return null

  if (!(await isSetupDone(request))) return null

  const gateUrl = new URL(`${API_URL}/auth/oidc/login`, request.url)
  gateUrl.searchParams.set('from', sanitizeFrom(searchParams.get('from')))
  return NextResponse.redirect(gateUrl, 307)
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  if (pathname === '/login') {
    const redirect = await handleLoginRoute(request)
    if (redirect) return redirect
  }

  // Always allow public routes
  if (isPublicRoute(pathname)) {
    return NextResponse.next()
  }

  // Check if setup is needed — redirect to /setup if no superadmin exists
  // Uses a cookie cache to avoid calling the API on every request
  const setupDone = request.cookies.get('ff_setup_done')?.value
  if (!setupDone) {
    try {
      const res = await fetch(`${API_URL}/setup/status`, {
        next: { revalidate: 60 }, // Cache for 60 seconds
      })
      if (res.ok) {
        const data = await res.json()
        if (data.needs_setup) {
          return NextResponse.redirect(new URL('/setup', request.url))
        }
        // Setup is done — set cookie so we don't check again
        const response = NextResponse.next()
        response.cookies.set('ff_setup_done', '1', { path: '/', maxAge: 60 * 60 * 24 }) // 24 hours
        return response
      }
    } catch {
      // API unreachable — let the request through, the page will show errors
    }
  }

  // Check for auth tokens
  const accessToken = request.cookies.get('ff_access_token')?.value
  const refreshToken = request.cookies.get('ff_refresh_token')?.value

  if (!accessToken && !refreshToken) {
    const whop = request.cookies.get('ff_auth_provider')?.value === 'whop' || request.headers.has('x-whop-user-token')
    const loginUrl = new URL(whop ? '/whop' : '/login', request.url)
    loginUrl.searchParams.set('from', pathname + request.nextUrl.search)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    /*
     * Match all paths except:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico
     * - api routes
     * - public assets (images, fonts, etc.)
     */
    '/((?!_next/static|_next/image|favicon\\.ico|api/|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|woff|woff2|ttf|otf)).*)',
  ],
}
