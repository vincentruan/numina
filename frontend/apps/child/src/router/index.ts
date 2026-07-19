import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore, setUser } from '@numina/auth'
import { getMainBaseUrl } from '@/utils/mainApp'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { globalLoadingCount, completeGlobalLoading, registerRouterTimeout, clearRouterTimeout } from '@/composables/usePageLoading'

NProgress.configure({ showSpinner: true, parent: '#app' })

// Child routes — all require authentication, redirect to unified login if not authenticated
const GUEST_ROUTES: string[] = []

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    // Authenticated child routes
    {
      path: '/',
      component: () => import('@/layouts/ChildLayout.vue'),
      children: [
        {
          path: '',
          name: 'ChildHome',
          component: () => import('@/pages/ChildHomePage.vue'),
          meta: { hasSkeleton: true }
        },
        {
          path: 'tasks',
          name: 'ChildTasks',
          component: () => import('@/pages/ChildTasksPage.vue'),
          meta: { hasSkeleton: true }
        },
        {
          path: 'ledger',
          name: 'ChildLedger',
          component: () => import('@/pages/ChildLedgerPage.vue'),
          meta: { hasSkeleton: true }
        },
        {
          path: 'wishes',
          name: 'ChildWishes',
          component: () => import('@/pages/ChildWishesPage.vue'),
          meta: { hasSkeleton: true }
        },
        {
          path: 'wishes/new',
          name: 'ChildWishCreate',
          component: () => import('@/pages/ChildWishCreatePage.vue'),
        },
        {
          path: 'wishes/:id',
          name: 'ChildWishDetail',
          component: () => import('@/pages/ChildWishDetailPage.vue'),
          meta: { hasSkeleton: true }
        },
        {
          path: 'assets/:id',
          name: 'ChildAssetDetail',
          component: () => import('@/pages/ChildAssetDetailPage.vue'),
          meta: { hasSkeleton: true }
        },
        {
          path: 'treasures',
          name: 'ChildTreasures',
          component: () => import('@/pages/ChildTreasuresPage.vue'),
          meta: { hasSkeleton: true }
        },
        {
          path: 'blind-box',
          redirect: '/treasures',
        },
        {
          path: 'calendar/day',
          name: 'ChildDayDetail',
          component: () => import('@/pages/ChildDayDetailPage.vue'),
          meta: { hasSkeleton: true }
        },
        {
          path: 'settings',
          name: 'ChildSettings',
          component: () => import('@/pages/ChildSettingsPage.vue'),
        },
      ],
    },
    // Catch-all redirect — must stay within child app
    // Redirect to child home, which will trigger auth check if needed.
    // Use router-internal '/' (resolves to URL /child/ via history base);
    // '/child/' here would be parsed as /child/child/, retriggering this rule infinitely.
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

// Cache the child session verification result to avoid repeated API calls
let childSessionVerified = false
let verificationInProgress = false

/**
 * Verify child session via API (cookie-based, works across ports in dev mode).
 * Returns true if user is authenticated with role='child'.
 */
async function verifyChildSession(): Promise<boolean> {
  // Return cached result if already verified
  if (childSessionVerified) {
    return true
  }

  // Avoid concurrent verification calls
  if (verificationInProgress) {
    return false
  }

  verificationInProgress = true
  try {
    const authStore = useAuthStore()
    await authStore.fetchMe()
    const user = authStore.user
    if (user?.role === 'child') {
      // Cache user in child app's localStorage for subsequent checks
      setUser(user)
      childSessionVerified = true
      return true
    }
    return false
  } catch {
    // API call failed - user not authenticated
    return false
  } finally {
    verificationInProgress = false
  }
}

router.beforeEach(async (to, _from, next) => {
  NProgress.start()

  // Check cached localStorage first (fast path)
  const authStore = useAuthStore()
  const cachedUser = authStore.user

  // If we already have a cached child user, proceed without API call
  if (cachedUser?.role === 'child') {
    next()
    return
  }

  // Need to verify session via API (first entry or localStorage empty)
  const isChildSession = await verifyChildSession()

  if (!isChildSession) {
    // Clean up NProgress before external redirect
    NProgress.done()
    // Build redirect URL preserving the original path
    const redirectPath = to.path !== '/' ? `/child${to.path}` : '/child/'
    const baseUrl = getMainBaseUrl()
    window.location.href = `${baseUrl}/login?redirect=${encodeURIComponent(redirectPath)}`
    next(false)
    return
  }

  next()
})

router.afterEach((to) => {
  // Pages with skeleton: complete immediately, clear any pending timeout
  if (to.meta.hasSkeleton) {
    clearRouterTimeout()
    NProgress.done()
    return
  }

  // Pages without skeleton: defer to page's usePageLoading
  // Safety timeout: force-complete after 5s (handles both idle and stuck cases)
  // - If page never called increment(): completes idle NProgress
  // - If page called increment() but hung: force-completes stuck loading
  // - If page called increment() within 5s: timeout cleared by increment(), page controls
  const timeoutId = setTimeout(() => {
    completeGlobalLoading()
  }, 5000)
  registerRouterTimeout(timeoutId)
})

export default router
