import { createRouter, createWebHistory } from 'vue-router'
import { getUser } from '@/utils/storage'
import { getChildBaseUrl } from '@/utils/childApp'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { completeGlobalLoading, registerRouterTimeout, markRouterNprogressActive } from '@/composables/usePageLoading'

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
      path: '/logout',
      name: 'Logout',
      component: () => import('@/pages/LogoutPage.vue'),
      meta: { guest: true }
    },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      children: [
        {
          path: '',
          name: 'Dashboard',
          component: () => import('@/pages/DashboardPage.vue'),
          meta: { hasSkeleton: true }
        },
        {
          path: 'dashboard/analytics',
          name: 'AssetAnalytics',
          component: () => import('@/pages/AssetAnalyticsPage.vue')
        },
        {
          // U6: standalone asset list removed — redirect to the finance hub assets tab.
          path: 'assets',
          redirect: { path: '/finance', query: { tab: 'assets' } }
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
          // U6: standalone liability list removed — redirect to the finance hub liabilities
          // tab. Preserve the W5 `focus` deep-link param (e.g. focus=liability_strategy).
          path: 'liabilities',
          redirect: (to) => ({ path: '/finance', query: { ...to.query, tab: 'liabilities' } })
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
          // U6: standalone wish list removed — redirect to the finance hub wishes tab.
          path: 'wishes',
          redirect: { path: '/finance', query: { tab: 'wishes' } }
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
          // N1 finance hub: unified entry for assets/liabilities/wishes.
          // Sub-tab ?tab= contract honored by FinanceHubPage onMounted.
          path: 'finance',
          name: 'FinanceHub',
          component: () => import('@/pages/FinanceHubPage.vue'),
          meta: { hasSkeleton: true }
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
          component: () => import('@/pages/BabyPage.vue'),
          meta: { hasSkeleton: true }
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
          path: 'settings/ai/asr',
          name: 'ASRConfig',
          component: () => import('@/pages/ASRConfigPage.vue'),
        },
        {
          path: 'settings/ai/asr/new',
          name: 'ASRConfigNew',
          component: () => import('@/pages/ASRProviderFormPage.vue'),
        },
        {
          path: 'settings/ai/asr/:id/edit',
          name: 'ASRConfigEdit',
          component: () => import('@/pages/ASRProviderFormPage.vue'),
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
          path: 'settings/family/config',
          name: 'FamilyConfig',
          component: () => import('@/pages/FamilyConfigPage.vue'),
        },
        {
          path: 'settings/family/debt-thresholds',
          name: 'DebtThresholds',
          component: () => import('@/pages/DebtThresholdsPage.vue'),
        },
        {
          path: 'settings/user/config',
          name: 'UserConfig',
          component: () => import('@/pages/UserConfigPage.vue'),
        },
        {
          path: 'ai/report',
          name: 'AIReport',
          component: () => import('@/pages/AIReportPage.vue')
        },
        {
          path: 'ai/chat/history',
          name: 'ChatHistory',
          component: () => import('@/pages/ChatHistoryPage.vue')
        },
        {
          path: 'ai/chat',
          name: 'AIChat',
          component: () => import('@/pages/AIChatPage.vue'),
          meta: { hasSkeleton: true }
        },
        {
          path: 'ai/time-machine',
          name: 'AITimeMachine',
          component: () => import('@/pages/AITimeMachinePage.vue')
        },
        {
          path: 'ai',
          name: 'AIHub',
          component: () => import('@/pages/AIHubPage.vue'),
          meta: { hasSkeleton: true }
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
        },
        {
          path: 'baby/literacy-report',
          name: 'LiteracyReport',
          component: () => import('@/pages/LiteracyReportPage.vue')
        },
        {
          path: 'manifesto/template-select',
          name: 'ManifestoTemplateSelect',
          component: () => import('@/pages/ManifestoTemplateSelectPage.vue'),
          meta: { requiresAuth: true },
        },
        {
          path: 'manifesto/edit',
          name: 'ManifestoEdit',
          component: () => import('@/pages/ManifestoEditPage.vue'),
          meta: { requiresAuth: true },
        },
        {
          path: 'manifesto/preview',
          name: 'ManifestoPreview',
          component: () => import('@/pages/ManifestoPreviewPage.vue'),
          meta: { requiresAuth: true },
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
        window.location.replace(getChildBaseUrl())
        // Return false to abort the in-SPA navigation so the URL doesn't briefly
        // change to /child before the full reload lands.
        return false
      }
    }
  ]
})

router.beforeEach((to, _from, next) => {
  NProgress.start()
  markRouterNprogressActive()

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
    window.location.replace(getChildBaseUrl())
    return
  }

  // Defense-in-depth: only known adult roles may access the main app.
  // Any unknown/future role (not owner or member) is denied — prevents
  // accidental access if a new non-adult role is added to the system.
  if (isLoggedIn && user!.role !== 'owner' && user!.role !== 'member') {
    next('/login')
    return
  }

  // Not logged in accessing protected route — redirect to login
  if (!isLoggedIn) {
    next('/login')
    return
  }

  // Adult user (owner or member) accessing protected route — allow
  next()
})

router.afterEach((_to) => {
  // Unified lifecycle: all pages (including hasSkeleton) go through the same
  // timeout. Pages that call increment() before the timeout take over NProgress
  // control; pages without async work auto-complete via this timeout.
  // This prevents the flicker caused by start→done→start across router/page.
  //
  // Timeout must exceed the Transition out-in delay (~150ms leave + ~150ms
  // enter = ~300ms worst case) so increment() always fires before the timeout.
  // 500ms covers the transition plus a generous GC / scheduler buffer.
  const timeoutId = setTimeout(() => {
    completeGlobalLoading()
  }, 500)
  registerRouterTimeout(timeoutId)
})

export default router
