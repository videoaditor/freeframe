import { describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

describe('public link previews', () => {
  it('publishes the approved square blue check for crawlers at the configured origin', async () => {
    vi.stubEnv('NEXT_PUBLIC_SITE_URL', 'https://reviews.example.test')
    try {
      const { metadata } = await import('../layout')
      expect(metadata.metadataBase?.origin).toBe('https://reviews.example.test')
      expect(metadata.openGraph).toMatchObject({
        title: 'AutoReview',
        images: [{ url: '/autoreview-check-v2.png', width: 512, height: 512 }],
      })
      expect(metadata.twitter).toMatchObject({
        card: 'summary',
        images: [{ url: '/autoreview-check-v2.png' }],
      })
      const png = readFileSync(join(__dirname, '../../public/autoreview-check-v2.png'))
      expect(png.readUInt32BE(16)).toBe(512)
      expect(png.readUInt32BE(20)).toBe(512)
    } finally {
      vi.unstubAllEnvs()
    }
  })
})
