import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSSE } from '../use-sse'

// Hoisted so the same mock object survives the `vi.resetModules()` the
// relative-URL suite needs, and so each test can set its own token outcome.
const authMock = vi.hoisted(() => ({
  getUsableAccessToken: vi.fn<() => Promise<string | null>>(),
}))
vi.mock('@/lib/auth', () => authMock)

// Connecting now awaits a token renewal, so the EventSource is created a
// microtask later than it used to be. Every assertion about instances has to
// let that settle first.
async function settle() {
  await act(async () => {})
}

// Mock EventSource
class MockEventSource {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSED = 2

  url: string
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {}
  closed = false

  constructor(url: string) {
    this.url = url
    MockEventSource.instances.push(this)
  }

  addEventListener(type: string, handler: (e: MessageEvent) => void) {
    if (!this.listeners[type]) {
      this.listeners[type] = []
    }
    this.listeners[type].push(handler)
  }

  removeEventListener(type: string, handler: (e: MessageEvent) => void) {
    if (this.listeners[type]) {
      this.listeners[type] = this.listeners[type].filter((h) => h !== handler)
    }
  }

  close() {
    this.closed = true
  }

  // Test helper: emit a named event
  emit(type: string, data: unknown) {
    const event = { data: JSON.stringify(data) } as MessageEvent
    this.listeners[type]?.forEach((fn) => fn(event))
  }

  static instances: MockEventSource[] = []
  static reset() {
    MockEventSource.instances = []
  }
}

describe('useSSE hook', () => {
  beforeEach(() => {
    MockEventSource.reset()
    authMock.getUsableAccessToken.mockReset()
    authMock.getUsableAccessToken.mockResolvedValue('test-token')
    vi.stubGlobal('EventSource', MockEventSource)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('creates EventSource with correct URL', async () => {
    renderHook(() => useSSE('project-123'))
    await settle()
    expect(MockEventSource.instances).toHaveLength(1)
    expect(MockEventSource.instances[0].url).toContain('/events/project-123')
  })

  it('includes access token in URL query param', async () => {
    renderHook(() => useSSE('project-123'))
    await settle()
    expect(MockEventSource.instances[0].url).toContain('token=test-token')
  })

  it('does not create EventSource when projectId is null', async () => {
    renderHook(() => useSSE(null))
    await settle()
    expect(MockEventSource.instances).toHaveLength(0)
  })

  it('does not create EventSource when enabled is false', async () => {
    renderHook(() => useSSE('project-123', { enabled: false }))
    await settle()
    expect(MockEventSource.instances).toHaveLength(0)
  })

  it('sets isConnected to true when connection opens', async () => {
    const { result } = renderHook(() => useSSE('project-123'))
    await settle()
    expect(result.current.isConnected).toBe(false)
    act(() => {
      MockEventSource.instances[0].onopen?.()
    })
    expect(result.current.isConnected).toBe(true)
  })

  it('sets isConnected to false and closes on error', async () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useSSE('project-123'))
    await settle()

    act(() => {
      MockEventSource.instances[0].onopen?.()
    })
    expect(result.current.isConnected).toBe(true)

    act(() => {
      MockEventSource.instances[0].onerror?.()
    })
    expect(result.current.isConnected).toBe(false)
    expect(MockEventSource.instances[0].closed).toBe(true)

    vi.useRealTimers()
  })

  it('calls onNewComment callback when new_comment event fires', async () => {
    const onNewComment = vi.fn()
    renderHook(() => useSSE('project-123', { onNewComment }))
    await settle()

    act(() => {
      MockEventSource.instances[0].emit('new_comment', {
        asset_id: 'a1',
        comment_id: 'c1',
        author: 'Alice',
      })
    })

    expect(onNewComment).toHaveBeenCalledWith({
      asset_id: 'a1',
      comment_id: 'c1',
      author: 'Alice',
    })
  })

  it('cleans up EventSource on unmount', async () => {
    const { unmount } = renderHook(() => useSSE('project-123'))
    await settle()
    const instance = MockEventSource.instances[0]
    unmount()
    expect(instance.closed).toBe(true)
  })

  it('schedules reconnect with backoff after error', async () => {
    vi.useFakeTimers()
    renderHook(() => useSSE('project-123'))
    await settle()

    act(() => {
      MockEventSource.instances[0].onerror?.()
    })

    // After error, no new instance yet (waiting for timer)
    expect(MockEventSource.instances).toHaveLength(1)

    // After backoff delay (1000ms), a new EventSource should be created
    await act(async () => {
      vi.advanceTimersByTime(1100)
    })
    expect(MockEventSource.instances).toHaveLength(2)

    vi.useRealTimers()
  })

  it('reconnects with a renewed token rather than the one that just failed', async () => {
    // The bug this guards: the token rides in the query string because
    // EventSource cannot send headers, and the endpoint answers an expired one
    // with 403. Reconnecting with the same dead token just repeats the 403 -
    // production logs showed hours of that, all carrying a token which had
    // expired that morning.
    vi.useFakeTimers()
    authMock.getUsableAccessToken
      .mockResolvedValueOnce('token-before')
      .mockResolvedValueOnce('token-after')

    renderHook(() => useSSE('project-123'))
    await settle()
    expect(MockEventSource.instances[0].url).toContain('token=token-before')

    act(() => {
      MockEventSource.instances[0].onerror?.()
    })
    await act(async () => {
      vi.advanceTimersByTime(1100)
    })

    expect(MockEventSource.instances[1].url).toContain('token=token-after')
    vi.useRealTimers()
  })

  it('stops reconnecting once the session can no longer be renewed', async () => {
    // A few retries absorb a network having a bad minute. Past that there is
    // nothing left to authenticate with, and retrying forever is pure noise.
    vi.useFakeTimers()
    authMock.getUsableAccessToken.mockResolvedValue(null)

    renderHook(() => useSSE('project-123'))
    await settle()

    for (const step of [1100, 2100, 4100, 8100]) {
      await act(async () => {
        vi.advanceTimersByTime(step)
      })
    }

    expect(MockEventSource.instances).toHaveLength(0)
    expect(authMock.getUsableAccessToken).toHaveBeenCalledTimes(3)
    vi.useRealTimers()
  })
})

describe('useSSE with relative NEXT_PUBLIC_API_URL', () => {
  beforeEach(() => {
    MockEventSource.reset()
    authMock.getUsableAccessToken.mockReset()
    authMock.getUsableAccessToken.mockResolvedValue('test-token')
    vi.stubGlobal('EventSource', MockEventSource)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  // Regression for issue #46: deployments behind nginx set NEXT_PUBLIC_API_URL
  // to a relative path like "/api". `new URL("/api/events/abc")` throws
  // "Failed to construct 'URL': Invalid URL" without a base, crashing the
  // dashboard the moment UploadSSEBridge first opens an SSE connection.
  it('builds a valid URL when NEXT_PUBLIC_API_URL is a relative path', async () => {
    vi.stubEnv('NEXT_PUBLIC_API_URL', '/api')
    vi.resetModules()
    const { useSSE: useSSEFresh } = await import('../use-sse')

    expect(() => renderHook(() => useSSEFresh('project-123'))).not.toThrow()
    await settle()
    expect(MockEventSource.instances).toHaveLength(1)
    expect(MockEventSource.instances[0].url).toContain('/api/events/project-123')
  })
})
