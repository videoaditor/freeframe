/**
 * Whether a cold, signed-out hit to /login should bounce straight to the gate.
 * Mirrors aditor-hub's shouldBounceToGateEarly: a gate failure comes back here
 * as `?error=...`, and auto-redirecting in that case would just replay the
 * same failure forever instead of showing it.
 */
export function shouldBounceToGateEarly(search: URLSearchParams): boolean {
  return !search.has('error')
}
