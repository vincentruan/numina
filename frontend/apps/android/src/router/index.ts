import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  // Hash history works in both Capacitor WebView and browser dev mode.
  // The shell never needs clean URLs — it's a configuration screen,
  // not a content app. After setup, the WebView navigates away entirely.
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'setup',
      component: () => import('@/pages/SetupPage.vue'),
    },
    {
      path: '/advanced',
      name: 'advanced',
      component: () => import('@/pages/AdvancedSettingsPage.vue'),
    },
  ],
})

export default router
