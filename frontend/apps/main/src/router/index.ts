import { createRouter, createWebHistory } from 'vue-router'
import { getUser } from '@/utils/storage'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'

NProgress.configure({ showSpinner: true, parent: '#app' })

const router = createRouter({
  history: createWebHistory('/'),
  scrollBehavior: () => ({ top: 0 }),
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
          path: 'dashboard/analytics',
          name: 'AssetAnalytics',
          component: () => import('@/pages/AssetAnalyticsPage.vue')
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
          path: 'blind-box/draws',
          name: 'BlindBoxDraws',
          component: () => import('@/pages/BlindBoxDrawsPage.vue')
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
          path: 'family/children/:childId/reset',
          name: 'ChildReset',
          component: () => import('@/pages/ChildResetPage.vue')
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
          path: 'settings/ai/provider/new',
          name: 'AIProviderCreate',
          component: () => import('@/pages/AIProviderFormPage.vue')
        },
        {
          path: 'settings/ai/provider/:id/edit',
          name: 'AIProviderEdit',
          component: () => import('@/pages/AIProviderFormPage.vue')
        },
        {
          path: 'settings/ai/mcp',
          name: 'MCPManage',
          component: () => import('@/pages/MCPManagePage.vue')
        },
        {
          path: 'settings/ai/web-search',
          name: 'WebSearch',
          component: () => import('@/pages/WebSearchPage.vue'),
        },
        {
          path: 'settings/ai/web-search/form',
          name: 'WebSearchForm',
          component: () => import('@/pages/WebSearchFormPage.vue'),
        },
        {
          path: 'settings/ai/skills',
          name: 'SkillsManage',
          component: () => import('@/pages/SkillsManagePage.vue')
        },
        {
          path: 'settings/ai/agents',
          name: 'AgentsManage',
          component: () => import('@/pages/AgentsManagePage.vue')
        },
        {
          path: 'settings/ai/agents/new',
          name: 'AgentCreate',
          component: () => import('@/pages/AgentFormPage.vue')
        },
        {
          path: 'settings/ai/agents/:id/edit',
          name: 'AgentEdit',
          component: () => import('@/pages/AgentFormPage.vue')
        },
        {
          path: 'settings/devices',
          name: 'Devices',
          component: () => import('@/pages/DevicesPage.vue')
        },
        {
          path: 'settings/notifications',
          name: 'NotificationConfig',
          component: () => import('@/pages/NotificationConfigPage.vue'),
        },
        {
          path: 'settings/notifications/threshold',
          name: 'NotificationThreshold',
          component: () => import('@/pages/NotificationThresholdPage.vue'),
        },
        {
          path: 'settings/password',
          name: 'ChangePassword',
          component: () => import('@/pages/ChangePasswordPage.vue'),
        },
        {
          path: 'settings/second-factor',
          name: 'ChangeSecondFactor',
          component: () => import('@/pages/ChangeSecondFactorPage.vue'),
        },
        {
          path: 'settings/import-report',
          name: 'ImportReport',
          component: () => import('@/pages/ImportReportPage.vue'),
        },
        {
          path: 'settings/family/coin-rates',
          name: 'CoinRates',
          component: () => import('@/pages/CoinRatesPage.vue'),
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
          path: 'ai/spending-leaks',
          name: 'AISpendingLeaks',
          component: () => import('@/pages/SpendingLeaksPage.vue')
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
          path: 'baby/chores/new',
          name: 'BabyChoreCreate',
          component: () => import('@/pages/BabyChoreCreatePage.vue')
        },
        {
          path: 'family/chore-approvals',
          name: 'ChoreApprovals',
          component: () => import('@/pages/ChoreApprovalsPage.vue')
        },
        {
          path: 'baby/chore-templates',
          name: 'ChoreTemplates',
          component: () => import('@/pages/BabyChoreTemplatesPage.vue')
        },
        {
          path: 'baby/chore-templates/:id/edit',
          name: 'ChoreTemplateEdit',
          component: () => import('@/pages/BabyChoreTemplateEditPage.vue')
        }
      ]
    },
    {
      // Match /child and any sub-path so navigation from inside the adult app
      // (e.g. via test fixtures) lands on a route that can hand off to the child SPA.
      // Use beforeEnter so we can call window.location.replace without Vue Router
      // racing us to a /'fallback' route in the same tick.
      path: '/child/:pathMatch(.*)*',
      // Component is a no-op placeholder; beforeEnter does the hand-off.
      component: { template: '<div />' },
      beforeEnter: () => {
        // Nginx routes /child/* to frontend/apps/child container.
        // window.location.replace forces a full reload, bypassing the SPA router.
        window.location.replace('/child/')
        // Return false to abort the in-SPA navigation so the URL doesn't briefly
        // change to /child before the full reload lands.
        return false
      }
    }
  ]
})

router.beforeEach((to, _from, next) => {
  NProgress.start()

  // /child/* paths belong to the child SPA (nginx routes /child/* to frontend-child).
  // The /child route handler does window.location.replace('/child/') to bounce
  // any stale in-app navigation. Skip the adult-app auth checks so unauthenticated
  // and stale adult sessions still hand off to the child SPA correctly.
  if (to.path === '/child' || to.path.startsWith('/child/')) {
    next()
    return
  }

  const user = getUser()
  const isLoggedIn = !!user
  const isChild = user?.role === 'child'

  // Guest routes (login, register, join-family) — allow even for stale child sessions
  // Child users with stale localStorage need to reach /login for re-authentication.
  // Note: Child users can also see /register and /join-family, but backend will
  // reject their submissions (role validation). This is safe because auth state
  // is determined by httpOnly cookies, not localStorage.
  if (to.meta.guest) {
    if (isLoggedIn && !isChild) {
      // Logged-in adult user accessing guest route → redirect to dashboard
      next('/')
    } else {
      // Not logged in, or child user (possibly stale session) → allow guest route
      next()
    }
    return
  }

  // Stale child session accessing protected route — redirect to child app
  if (isChild) {
    window.location.replace('/child/')
    return
  }

  // Not logged in accessing protected route — redirect to login
  if (!isLoggedIn) {
    next('/login')
    return
  }

  // Adult user accessing protected route — allow
  next()
})

router.afterEach(() => {
  NProgress.done()
})

export default router
