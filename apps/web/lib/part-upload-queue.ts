/** Shared per-screen queue: separate file drops still share the same uplink budget. */
export function createUploadQueue(limit = 2) {
  let active = 0
  const waiting: (() => void)[] = []
  return async <T>(work: () => Promise<T>): Promise<T> => {
    if (active >= limit) await new Promise<void>(resolve => waiting.push(resolve))
    else active++
    try { return await work() }
    finally { const next = waiting.shift(); if (next) next(); else active-- }
  }
}
