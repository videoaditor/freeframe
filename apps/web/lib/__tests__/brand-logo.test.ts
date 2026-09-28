import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api } from '../api'
import { getBrandLogo, uploadBrandLogo } from '../platform'
vi.mock('../api', () => ({ api: { post: vi.fn(), put: vi.fn(), get: vi.fn() } }))
const file = new File(['image'], 'logo.png', { type: 'image/png' })
beforeEach(() => {
  vi.resetAllMocks()
  vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue({ width: 1000, height: 250, close: vi.fn() }))
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage: vi.fn() } as unknown as CanvasRenderingContext2D)
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (callback) { callback(new Blob(['webp'], { type: 'image/webp' })) })
  vi.mocked(api.post).mockResolvedValue({ upload_url: 'https://storage.test/signed', key: 'branding/p1/logo/new.webp' })
  vi.mocked(api.put).mockResolvedValue({ logo_url: 'https://storage.test/logo.webp' })
})
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })
it('uploads WebP bytes to the signed URL before saving the key to this project', async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: true }); vi.stubGlobal('fetch', fetcher)
  expect(await uploadBrandLogo('p1', file)).toBe('https://storage.test/logo.webp')
  expect(api.post).toHaveBeenCalledWith('/projects/p1/branding/logo-upload', {})
  expect(fetcher).toHaveBeenCalledWith('https://storage.test/signed', { method: 'PUT', headers: { 'content-type': 'image/webp' }, body: expect.any(Blob) })
  expect(api.put).toHaveBeenCalledWith('/projects/p1/branding', { logo_s3_key: 'branding/p1/logo/new.webp' })
  expect(fetcher.mock.invocationCallOrder[0]).toBeLessThan(vi.mocked(api.put).mock.invocationCallOrder[0])
})
it('never replaces the stored logo when object upload fails', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
  await expect(uploadBrandLogo('p1', file)).rejects.toThrow('did not upload')
  expect(api.put).not.toHaveBeenCalled()
})
it('propagates branding read errors so the owner can retry', async () => {
  vi.mocked(api.get).mockRejectedValue(new Error('offline'))
  await expect(getBrandLogo('p1')).rejects.toThrow('offline')
})
it('rejects a browser conversion fallback instead of uploading PNG bytes as WebP', async () => {
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(callback => callback(new Blob(['png'], { type: 'image/png' })))
  vi.stubGlobal('fetch', vi.fn())
  await expect(uploadBrandLogo('p1', file)).rejects.toThrow('WebP')
  expect(api.put).not.toHaveBeenCalled()
})
