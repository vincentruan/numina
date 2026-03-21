import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/utils/storage'

const router = createRouter({
  history: createWebHistory('/numina/'),
  routes: [
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
          path: 'family',
          name: 'Family',
          component: () => import('@/pages/FamilyPage.vue')
        },
        {
          path: 'family/members',
          name: 'MemberManage',
          component: () => import('@/pages/MemberManagePage.vue')
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
        }
      ]
    }
  ]
})

router.beforeEach((to, _from, next) => {
  const token = getToken()
  if (to.meta.guest) {
    if (token) {
      next('/')
    } else {
      next()
    }
  } else {
    if (!token) {
      next('/login')
    } else {
      next()
    }
  }
})

export default router
