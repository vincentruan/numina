<template>
  <van-tabbar :model-value="activeTab" @change="onTabChange">
    <van-tabbar-item name="dashboard" icon="chart-trending-o">{{ t('nav.dashboard') }}</van-tabbar-item>
    <van-tabbar-item name="wishes" icon="star-o">{{ t('nav.wishes') }}</van-tabbar-item>
    <van-tabbar-item name="ai" aria-label="AI 智能助手">
      <template #icon="{ active: isActive }">
        <AIBrainIcon :active="isActive" />
      </template>
    </van-tabbar-item>
    <van-tabbar-item name="liabilities" icon="bill-o">{{ t('nav.liabilities') }}</van-tabbar-item>
    <van-tabbar-item v-if="isOwner" name="baby" icon="friends-o">{{ t('nav.baby') }}</van-tabbar-item>
    <van-tabbar-item name="settings" icon="setting-o">{{ t('nav.settings') }}</van-tabbar-item>
  </van-tabbar>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import AIBrainIcon from './AIBrainIcon.vue'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const isOwner = computed(() => authStore.user?.role === 'owner')

const routeToTab: Record<string, string> = {
  '/': 'dashboard',
  '/wishes': 'wishes',
  '/liabilities': 'liabilities',
  '/baby': 'baby',
  '/settings': 'settings',
  '/ai': 'ai',
}

const activeTab = computed(() => {
  const path = route.path
  return routeToTab[path] ?? 'dashboard'
})

const tabToRoute: Record<string, string> = {
  dashboard: '/',
  wishes: '/wishes',
  liabilities: '/liabilities',
  baby: '/baby',
  settings: '/settings',
  ai: '/ai',
}

function onTabChange(name: string | number) {
  if (typeof name !== 'string') return
  const target = tabToRoute[name]
  if (target && route.path !== target) {
    router.push(target)
  }
}
</script>
