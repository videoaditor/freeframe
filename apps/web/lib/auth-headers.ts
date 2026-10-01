/** Whop's app proxy strips Authorization. Both headers carry the same session. */
export function authHeaders(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}`, 'X-FreeFrame-Token': token } : {}
}
