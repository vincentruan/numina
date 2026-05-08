import { describe, expect, it, vi } from 'vitest'

vi.mock('@numina/auth', () => ({
  getUser: () => null,
  useLoadingOverlay: () => ({
    show: vi.fn(),
    hide: vi.fn(),
  }),
}))

describe('child auth route', () => {
  it('keeps the child login page mounted at /auth', async () => {
    const { default: router } = await import('./index')
    const route = router.getRoutes().find(r => r.path === '/auth')

    expect(route?.name).toBe('ChildAuth')
    expect(route?.meta.guest).toBe(true)
    expect(route?.components?.default).toBeTypeOf('function')
  })
})
