<template>
  <van-tabbar :model-value="activeTab" class="app-tabbar" :z-index="1000" @change="onTabChange">
    <van-tabbar-item name="dashboard" data-tab="dashboard" icon="chart-trending-o">{{ t('nav.dashboard') }}</van-tabbar-item>
    <van-tabbar-item name="finance" data-tab="finance" icon="balance-o">{{ t('nav.finance') }}</van-tabbar-item>
    <van-tabbar-item name="ai" data-tab="ai" :aria-label="t('settings.aiAssistant')">
      <template #icon="{ active: isActive }">
        <AIBrainIcon :active="isActive" />
      </template>
      {{ t('nav.ai') }}
    </van-tabbar-item>
    <van-tabbar-item v-if="isOwner" name="baby" data-tab="baby" icon="friends-o">{{ t('nav.baby') }}</van-tabbar-item>
    <van-tabbar-item name="settings" data-tab="settings" icon="setting-o">{{ t('nav.settings') }}</van-tabbar-item>
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

const activeTab = computed(() => {
  const path = route.path
  if (path === '/ai' || path.startsWith('/ai/')) return 'ai'
  if (path === '/settings' || path.startsWith('/settings/')) return 'settings'
  if (path === '/family' || path.startsWith('/family/')) return 'settings'
  if (path === '/baby' || path.startsWith('/baby/')) return 'baby'
  if (path.startsWith('/blind-box/')) return 'baby'
  if (path === '/chore-approvals') return 'baby'
  // KTD-2: finance hub covers assets/liabilities/wishes groups (path-prefix match,
  // covers all sub-routes incl. params). All three list paths now live under finance.
  if (path.startsWith('/assets') || path.startsWith('/liabilities')) return 'finance'
  if (path.startsWith('/finance')) return 'finance'
  if (path.startsWith('/wishes')) return 'finance'
  return 'dashboard'
})

const tabToRoute: Record<string, string> = {
  dashboard: '/',
  finance: '/finance',
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

<style scoped>
/* Force all tab items to share width equally regardless of count */
.app-tabbar :deep(.van-tabbar),
.app-tabbar {
  display: flex;
  z-index: 1000 !important;
}
.app-tabbar :deep(.van-tabbar-item) {
  flex: 1;
  min-width: 0;
  padding: 0 2px;
}
.app-tabbar :deep(.van-tabbar-item__text) {
  font-size: 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
