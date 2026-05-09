import { createRouter, createWebHistory } from 'vue-router'
import { getUser, useLoadingOverlay } from '@numina/auth'

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
        },
        {
          path: 'tasks',
          name: 'ChildTasks',
          component: () => import('@/pages/ChildTasksPage.vue'),
        },
        {
          path: 'ledger',
          name: 'ChildLedger',
          component: () => import('@/pages/ChildLedgerPage.vue'),
        },
        {
          path: 'wishes',
          name: 'ChildWishes',
          component: () => import('@/pages/ChildWishesPage.vue'),
        },
        {
          path: 'wishes/new',
          name: 'ChildWishCreate',
          component: () => import('@/pages/ChildWishCreatePage.vue'),
        },
        {
          path: 'treasures',
          name: 'ChildTreasures',
          component: () => import('@/pages/ChildTreasuresPage.vue'),
        },
        {
          path: 'blind-box',
          redirect: '/treasures',
        },
        {
          path: 'calendar/day',
          name: 'ChildDayDetail',
          component: () => import('@/pages/ChildDayDetailPage.vue'),
        },
      ],
    },
    // Catch-all redirect
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

router.beforeEach((to, _from, next) => {
  useLoadingOverlay().show()
  const user = getUser()
  const isChildSession = user?.role === 'child'

  // All routes in child app require authentication
  // Redirect unauthenticated users to unified login on main site
  if (!isChildSession) {
    // Build redirect URL preserving the original path
    const redirectPath = to.path !== '/' ? `/child${to.path}` : '/child/'
    window.location.href = `https://numina.xiaoshutiao.space/login?redirect=${encodeURIComponent(redirectPath)}`
    next(false)
    return
  }

  next()
})

router.afterEach(() => {
  useLoadingOverlay().hide()
})

export default router
