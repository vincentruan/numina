import { createRouter, createWebHistory } from 'vue-router'
import { getUser } from '@/utils/storage'

const router = createRouter({
  history: createWebHistory('/'),
  routes: [
    {
      path: '/welcome',
      name: 'Welcome',
      component: () => import('@/pages/WelcomeGatewayPage.vue'),
      meta: { guest: true }
    },
    {
      path: '/promo/family',
      name: 'FamilyPromo',
      component: () => import('@/pages/FamilyPromoPage.vue'),
      meta: { guest: true }
    },
    {
      path: '/promo/developer',
      name: 'DeveloperPromo',
      component: () => import('@/pages/DeveloperPromoPage.vue'),
      meta: { guest: true }
    },
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/pages/LoginPage.vue'),
      meta: { guest: true }
    },
    {
      path: '/register',
      name: 'Register',
      component: () => import('@/pages/RegisterPage.vue'),
      meta: { guest: true }
    },
    {
      path: '/join-family',
      name: 'JoinFamily',
      component: () => import('@/pages/JoinFamilyPage.vue'),
      meta: { guest: true }
    },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      children: [
        {
          path: '',
          name: 'Dashboard',
          component: () => import('@/pages/DashboardPage.vue')
        },
        {
          path: 'assets',
          name: 'AssetList',
          component: () => import('@/pages/AssetListPage.vue')
        },
        {
          path: 'assets/new',
          name: 'AssetCreate',
          component: () => import('@/pages/AssetFormPage.vue')
        },
        {
          path: 'assets/:id',
          name: 'AssetDetail',
          component: () => import('@/pages/AssetDetailPage.vue')
        },
        {
          path: 'assets/:id/edit',
          name: 'AssetEdit',
          component: () => import('@/pages/AssetFormPage.vue')
        },
        {
          path: 'assets/:id/sell',
          name: 'AssetSell',
          component: () => import('@/pages/AssetSellPage.vue')
        },
        {
          path: 'liabilities',
          name: 'LiabilityList',
          component: () => import('@/pages/LiabilityListPage.vue')
        },
        {
          path: 'liabilities/new',
          name: 'LiabilityCreate',
          component: () => import('@/pages/LiabilityFormPage.vue')
        },
        {
          path: 'liabilities/:id/edit',
          name: 'LiabilityEdit',
          component: () => import('@/pages/LiabilityFormPage.vue')
        },
        {
          path: 'liabilities/:id',
          name: 'LiabilityDetail',
          component: () => import('@/pages/LiabilityDetailPage.vue')
        },
        {
          path: 'wishes',
          name: 'WishList',
          component: () => import('@/pages/WishListPage.vue')
        },
        {
          path: 'wishes/new',
          name: 'WishCreate',
          component: () => import('@/pages/WishFormPage.vue')
        },
        {
          path: 'wishes/:id/edit',
          name: 'WishEdit',
          component: () => import('@/pages/WishFormPage.vue')
        },
        {
          path: 'wishes/:id',
          name: 'WishDetail',
          component: () => import('@/pages/WishDetailPage.vue')
        },
        {
          path: 'blind-box/gifts',
          name: 'BlindBoxGiftList',
          component: () => import('@/pages/BlindBoxGiftListPage.vue')
        },
        {
          path: 'blind-box/gifts/new',
          name: 'BlindBoxGiftCreate',
          component: () => import('@/pages/BlindBoxGiftFormPage.vue')
        },
        {
          path: 'blind-box/gifts/:id/edit',
          name: 'BlindBoxGiftEdit',
          component: () => import('@/pages/BlindBoxGiftFormPage.vue')
        },
        {
          path: 'blind-box/config',
          name: 'BlindBoxConfig',
          component: () => import('@/pages/BlindBoxConfigPage.vue')
        },
        {
          path: 'family',
          name: 'Family',
          component: () => import('@/pages/FamilyPage.vue')
        },
        {
          path: 'baby',
          name: 'Baby',
          component: () => import('@/pages/BabyPage.vue')
        },
        {
          path: 'settings',
          name: 'Settings',
          component: () => import('@/pages/SettingsPage.vue')
        },
        {
          path: 'settings/categories',
          name: 'CategoryManage',
          component: () => import('@/pages/CategoryManagePage.vue')
        },
        {
          path: 'settings/tags',
          name: 'TagManage',
          component: () => import('@/pages/TagManagePage.vue')
        },
        {
          path: 'settings/ai',
          name: 'AIConfig',
          component: () => import('@/pages/AIConfigPage.vue')
        },
        {
          path: 'settings/devices',
          name: 'Devices',
          component: () => import('@/pages/DevicesPage.vue')
        },
        {
          path: 'settings/notifications',
          component: () => import('@/pages/NotificationConfigPage.vue'),
        },
        {
          path: 'settings/import-report',
          name: 'ImportReport',
          component: () => import('@/pages/ImportReportPage.vue'),
        },
        {
          path: 'ai/report',
          name: 'AIReport',
          component: () => import('@/pages/AIReportPage.vue')
        },
        {
          path: 'ai/alerts',
          name: 'AIAlerts',
          component: () => import('@/pages/AIAlertsPage.vue')
        },
        {
          path: 'ai/disposal',
          name: 'AIDisposal',
          component: () => import('@/pages/AIDisposalPage.vue')
        },
        {
          path: 'ai/liability',
          name: 'AILiability',
          component: () => import('@/pages/AILiabilityAdvisorPage.vue')
        },
        {
          path: 'ai/chat',
          name: 'AIChat',
          component: () => import('@/pages/AIChatPage.vue')
        },
        {
          path: 'ai/time-machine',
          name: 'AITimeMachine',
          component: () => import('@/pages/AITimeMachinePage.vue')
        },
        {
          path: 'ai/allocation',
          name: 'AIAllocation',
          component: () => import('@/pages/AIAllocationPage.vue')
        },
        {
          path: 'ai',
          name: 'AIHub',
          component: () => import('@/pages/AIHubPage.vue')
        },
        {
          path: 'stats',
          name: 'DataStats',
          component: () => import('@/pages/DataStatsPage.vue')
        },
        {
          path: 'baby/calendar/day',
          name: 'BabyDayDetail',
          component: () => import('@/pages/BabyDayDetailPage.vue')
        },
        {
          path: 'chore-approvals',
          name: 'ChoreApprovals',
          component: () => import('@/pages/ChoreApprovalsPage.vue')
        },
        {
          path: 'wish-review',
          name: 'WishReview',
          component: () => import('@/pages/WishReviewPage.vue')
        }
      ]
    },
    {
      path: '/child',
      redirect: () => {
        // Nginx routes /child/* to frontend/apps/child container.
        // This redirect handles any stale in-app navigation to /child/* paths.
        window.location.replace('/child/')
        return '/'
      }
    }
  ]
})

router.beforeEach((to, _from, next) => {
  const user = getUser()
  const isLoggedIn = !!user
  const isChild = user?.role === 'child'

  // Stale child session — redirect to child app via full navigation
  if (isChild) {
    window.location.replace('/child/')
    return
  }

  // Guest routes (login, register, join-family)
  if (to.meta.guest) {
    if (isLoggedIn) {
      next('/')
    } else {
      next()
    }
    return
  }

  // Not logged in — redirect to login
  if (!isLoggedIn) {
    next('/login')
    return
  }

  // Adult user — allow
  next()
})

export default router
