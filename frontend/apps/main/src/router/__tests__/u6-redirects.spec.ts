import { describe, it, expect, vi } from 'vitest'

// The router module imports storage (auth guard) + NProgress at load. Mock both so
// importing the real router is side-effect-free.
vi.mock('@/utils/storage', () => ({
  getUser: () => null,
}))
vi.mock('nprogress', () => ({
  default: { configure: vi.fn(), start: vi.fn(), done: vi.fn() },
}))
vi.mock('@/utils/childApp', () => ({
  getChildBaseUrl: () => 'http://localhost/child/',
}))
vi.mock('@/composables/usePageLoading', () => ({
  globalLoadingCount: { value: 0 },
  completeGlobalLoading: vi.fn(),
  registerRouterTimeout: vi.fn(),
  clearRouterTimeout: vi.fn(),
}))

import router from '@/router'
import type { RouteRecordRaw } from 'vue-router'

// router.getRoutes() returns flattened records with FULL paths (children expanded).
// Redirect routes are unnamed, so match by path.
function routeByPath(fullPath: string): RouteRecordRaw | undefined {
  return router.getRoutes().find((r) => r.path === fullPath) as RouteRecordRaw | undefined
}

type RedirectTarget = { path?: string; query?: Record<string, unknown> }

function resolveRedirect(record: RouteRecordRaw, to: { path: string; query: Record<string, unknown> }): RedirectTarget {
  const r = record.redirect
  if (typeof r === 'function') return (r as (to: unknown) => RedirectTarget)(to)
  return (r ?? {}) as RedirectTarget
}

describe('router U6 redirects (AE3)', () => {
  it('/assets redirects to /finance?tab=assets', () => {
    const rec = routeByPath('/assets')
    expect(rec?.redirect).toBeTruthy()
    expect(resolveRedirect(rec!, { path: '/assets', query: {} })).toEqual({ path: '/finance', query: { tab: 'assets' } })
  })

  it('/wishes redirects to /finance?tab=wishes', () => {
    const rec = routeByPath('/wishes')
    expect(rec?.redirect).toBeTruthy()
    expect(resolveRedirect(rec!, { path: '/wishes', query: {} })).toEqual({ path: '/finance', query: { tab: 'wishes' } })
  })

  it('/liabilities redirects to /finance?tab=liabilities', () => {
    const rec = routeByPath('/liabilities')
    expect(rec?.redirect).toBeTruthy()
    expect(resolveRedirect(rec!, { path: '/liabilities', query: {} })).toEqual({ path: '/finance', query: { tab: 'liabilities' } })
  })

  it('/liabilities redirect preserves the W5 focus param', () => {
    const rec = routeByPath('/liabilities')
    const target = resolveRedirect(rec!, { path: '/liabilities', query: { focus: 'liability_strategy' } })
    expect(target.path).toBe('/finance')
    expect(target.query).toEqual({ tab: 'liabilities', focus: 'liability_strategy' })
  })

  it('detail/new/edit child routes still resolve to components (no redirect)', () => {
    for (const p of ['/assets/new', '/assets/:id', '/assets/:id/edit', '/assets/:id/sell', '/liabilities/new', '/liabilities/:id', '/liabilities/:id/edit', '/wishes/new', '/wishes/:id', '/wishes/:id/edit']) {
      const rec = routeByPath(p)
      expect(rec, `route ${p} should exist`).toBeTruthy()
      expect(rec!.redirect, `route ${p} must not redirect`).toBeFalsy()
      expect(rec!.components?.default, `route ${p} must have a component`).toBeTruthy()
    }
  })

  it('no longer registers AssetList / WishList / LiabilityList route names', () => {
    expect(router.hasRoute('AssetList')).toBe(false)
    expect(router.hasRoute('WishList')).toBe(false)
    expect(router.hasRoute('LiabilityList')).toBe(false)
    // Detail routes keep their names.
    expect(router.hasRoute('AssetDetail')).toBe(true)
    expect(router.hasRoute('LiabilityDetail')).toBe(true)
    expect(router.hasRoute('WishDetail')).toBe(true)
  })
})
