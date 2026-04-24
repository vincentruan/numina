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
  { name: 'BlindBoxGiftList', path: '/blind-box/gifts' },
  { name: 'BlindBoxGiftCreate', path: '/blind-box/gifts/new' },
  { name: 'BlindBoxGiftEdit', path: '/blind-box/gifts/1/edit' },
  { name: 'BlindBoxConfig', path: '/blind-box/config' },
  { name: 'Family', path: '/family' },
  { name: 'Baby', path: '/baby' },
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
  // Family — chore & wish management
  { name: 'ChoreApprovals', path: '/chore-approvals' },
  { name: 'WishReview', path: '/wish-review' },
  // Child routes (authenticated via child session)
  { name: 'ChildHome', path: '/child' },
  { name: 'ChildWishes', path: '/child/wishes' },
  { name: 'ChildTasks', path: '/child/tasks' },
  { name: 'ChildLedger', path: '/child/ledger' },
  { name: 'ChildTreasures', path: '/child/treasures' },
  { name: 'ChildBlindBox', path: '/child/blind-box' },
  { name: 'ChildDayDetail', path: '/child/calendar/day' },
  { name: 'BabyDayDetail', path: '/baby/calendar/day' },
]

/** Routes accessible only to guests. Authenticated access → redirect to / */
export const GUEST_ROUTES: RouteEntry[] = [
  { name: 'Login', path: '/login' },
  { name: 'Register', path: '/register' },
  { name: 'JoinFamily', path: '/join-family' },
  // Public promotional pages (guest-only, authenticated users redirect to dashboard)
  { name: 'Welcome', path: '/welcome' },
  { name: 'FamilyPromo', path: '/promo/family' },
  { name: 'DeveloperPromo', path: '/promo/developer' },
]

/**
 * Public routes — accessible regardless of adult auth state.
 * These are child-specific auth pages that use their own session mechanism.
 * Adult authenticated users are NOT redirected away from these routes.
 */
export const PUBLIC_ROUTES: RouteEntry[] = [
  { name: 'ChildSelect', path: '/child/select' },
  { name: 'ChildAuth', path: '/child/auth' },
  { name: 'ChildPinLogin', path: '/child/pin' },
  { name: 'ChildBind', path: '/child/bind' },
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
