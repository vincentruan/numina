/**
 * Canonical route manifest for auth-guard tests.
 *
 * Mirrors frontend/src/router/index.ts. When a route is added to the router,
 * add it here too — the sync-check test in auth-guards.spec.ts will fail if
 * any router route name is missing from this file.
 *
 * Parameterized routes use sentinel ID '1'. The guard tests only verify
 * redirect behaviour, not that the resource exists.
 */

export interface RouteEntry {
  name: string
  path: string
}

/** Routes that require authentication. Unauthenticated access → redirect to /login */
export const PROTECTED_ROUTES: RouteEntry[] = [
  { name: 'Dashboard', path: '/' },
  { name: 'AssetList', path: '/assets' },
  { name: 'AssetCreate', path: '/assets/new' },
  { name: 'AssetDetail', path: '/assets/1' },
  { name: 'AssetEdit', path: '/assets/1/edit' },
  { name: 'AssetSell', path: '/assets/1/sell' },
  { name: 'LiabilityList', path: '/liabilities' },
  { name: 'LiabilityCreate', path: '/liabilities/new' },
  { name: 'LiabilityEdit', path: '/liabilities/1/edit' },
  { name: 'LiabilityDetail', path: '/liabilities/1' },
  { name: 'WishList', path: '/wishes' },
  { name: 'WishCreate', path: '/wishes/new' },
  { name: 'WishEdit', path: '/wishes/1/edit' },
  { name: 'WishDetail', path: '/wishes/1' },
  { name: 'Family', path: '/family' },
  { name: 'MemberManage', path: '/family/members' },
  { name: 'Settings', path: '/settings' },
  { name: 'CategoryManage', path: '/settings/categories' },
  { name: 'TagManage', path: '/settings/tags' },
  { name: 'AIConfig', path: '/settings/ai' },
  { name: 'AIReport', path: '/ai/report' },
  { name: 'AIAlerts', path: '/ai/alerts' },
  { name: 'AIDisposal', path: '/ai/disposal' },
  { name: 'AILiability', path: '/ai/liability' },
  { name: 'AIChat', path: '/ai/chat' },
  { name: 'AIAllocation', path: '/ai/allocation' },
  { name: 'AIHub', path: '/ai' },
  { name: 'DataStats', path: '/stats' },
]

/** Routes accessible only to guests. Authenticated access → redirect to / */
export const GUEST_ROUTES: RouteEntry[] = [
  { name: 'Login', path: '/login' },
  { name: 'Register', path: '/register' },
  { name: 'JoinFamily', path: '/join-family' },
]

/**
 * Extract route names from the router source file using regex.
 * Used by the sync-check test to verify this manifest stays in sync
 * with frontend/src/router/index.ts without importing Vue/vue-router.
 */
export function extractRouteNamesFromSource(source: string): string[] {
  const matches = source.matchAll(/name:\s*['"](\w+)['"]/g)
  return Array.from(matches, (m) => m[1])
}
