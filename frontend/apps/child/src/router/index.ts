import { createRouter, createWebHistory } from 'vue-router'
import { getUser } from '@numina/auth'
import { getMainBaseUrl } from '@/utils/mainApp'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'

NProgress.configure({ showSpinner: true, parent: '#app' })

// Child routes — all require authentication, redirect to unified login if not authenticated
const GUEST_ROUTES: string[] = []

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
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

router.beforeEach((to, _from, next) => {
  NProgress.start()
  const user = getUser()
  const isChildSession = user?.role === 'child'

  // All routes in child app require authentication
  // Redirect unauthenticated users to unified login on main site
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
  // Pages with skeleton: immediately complete NProgress
  // Skeleton takes over visual feedback during data loading
  if (to.meta.hasSkeleton) {
    NProgress.done()
    return
  }

  // Pages without skeleton: complete NProgress after a short delay
  // This allows the page component to mount and potentially restart NProgress
  // for async data loading. Pages that don't need loading indicator will just
  // have the progress bar complete naturally.
  setTimeout(() => {
    NProgress.done()
  }, 100)
})

export default router
