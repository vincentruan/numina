import { createRouter, createWebHistory } from 'vue-router'
import { getUser, useLoadingOverlay } from '@numina/auth'

// Guest routes — accessible without child session
const GUEST_ROUTES = ['/auth']

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // Guest routes (child auth flow)
    {
      path: '/auth',
      name: 'ChildAuth',
      component: () => import('@/pages/ChildAuthPage.vue'),
      meta: { guest: true },
    },
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
  const isGuest = GUEST_ROUTES.includes(to.path) || to.meta?.guest

  if (isGuest) {
    // Guest routes: redirect to home if already authenticated
    if (isChildSession) {
      next('/')
    } else {
      next()
    }
  } else {
    // Protected routes: redirect to adult app if admin_child_view flag is stale (no active child session)
    if (!isChildSession) {
      if (localStorage.getItem('admin_child_view') !== null) {
        localStorage.removeItem('admin_child_view')
        window.location.replace('/')
        next(false)
        return
      }
      next('/auth')
    } else {
      next()
    }
  }
})

router.afterEach(() => {
  useLoadingOverlay().hide()
})

export default router
