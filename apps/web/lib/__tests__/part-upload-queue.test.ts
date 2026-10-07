import { expect, it } from 'vitest'
import { createUploadQueue } from '../part-upload-queue'
it('bounds concurrent transfers across separate drops and continues after failure', async () => {
  const queue = createUploadQueue(2)
  const running: number[] = []
  const release: (() => void)[] = []
  const work = (n: number) => queue(async () => { running.push(n); await new Promise<void>(resolve => release[n] = resolve); if (n === 0) throw new Error('retry'); return n })
  const a = work(0).catch(() => -1), b = work(1), c = work(2)
  await Promise.resolve()
  expect(running).toEqual([0, 1])
  release[0]()
  expect(await a).toBe(-1)
  await Promise.resolve()
  expect(running).toEqual([0, 1, 2])
  release[1](); release[2]()
  expect(await Promise.all([b, c])).toEqual([1, 2])
})
