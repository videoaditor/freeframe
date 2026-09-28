import { expect, it } from 'vitest'
import { useBrandingStore } from '../branding-store'

it('migrates the old app name while preserving custom branding', async () => {
  const migrate = useBrandingStore.persist.getOptions().migrate!
  expect(await migrate({ orgName: 'Aditor Review', orgLogoDark: null, orgLogoLight: null }, 2)).toMatchObject({ orgName: 'Autoreview' })
  const custom = { orgName: 'Studio', orgLogoDark: '/custom.png', orgLogoLight: null }
  expect(await migrate(custom, 2)).toMatchObject(custom)
})
