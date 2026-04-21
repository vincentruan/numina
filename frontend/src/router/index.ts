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
          path: 'family',
          name: 'Family',
          component: () => import('@/pages/FamilyPage.vue')
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
          path: 'baby',
          name: 'Baby',
          component: () => import('@/pages/BabyPage.vue')
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
      component: () => import('@/layouts/ChildLayout.vue'),
      children: [
        { path: '', name: 'ChildHome', component: () => import('@/pages/child/ChildHomePage.vue') },
        { path: 'wishes', name: 'ChildWishes', component: () => import('@/pages/child/ChildWishesPage.vue') },
        { path: 'tasks', name: 'ChildTasks', component: () => import('@/pages/child/ChildTasksPage.vue') },
        { path: 'ledger', name: 'ChildLedger', component: () => import('@/pages/child/ChildLedgerPage.vue') },
        { path: 'treasures', name: 'ChildTreasures', component: () => import('@/pages/child/ChildTreasuresPage.vue') },
        { path: 'select', name: 'ChildSelect', component: () => import('@/pages/ChildSelectPage.vue'), meta: { guest: true } },
        { path: 'auth', name: 'ChildAuth', component: () => import('@/pages/ChildAuthPage.vue'), meta: { guest: true } },
        { path: 'bind', name: 'ChildBind', component: () => import('@/pages/ChildBindPage.vue'), meta: { guest: true } },
      ]
    }
  ]
})

router.beforeEach((to, _from, next) => {
  const user = getUser()
  const isLoggedIn = !!user
  const isChild = user?.role === 'child'
  const isChildBindRoute = to.path.startsWith('/child/bind')

  // Child bind route — accessible without session
  if (isChildBindRoute) {
    next()
    return
  }

  // Guest routes (login, register, join-family)
  if (to.meta.guest) {
    if (isLoggedIn) {
      next(isChild ? '/child/' : '/')
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

  // Child user — only /child/* allowed
  if (isChild) {
    if (to.path.startsWith('/child')) {
      next()
    } else {
      next('/child/')
    }
    return
  }

  // Adult user — block /child/* routes
  if (to.path.startsWith('/child')) {
    next('/')
    return
  }

  // Adult user on adult route — allow
  next()
})

export default router
