<template>
  <van-tabbar :model-value="activeTab" class="app-tabbar" :z-index="1000" @change="onTabChange">
    <van-tabbar-item name="dashboard" icon="chart-trending-o">{{ t('nav.dashboard') }}</van-tabbar-item>
    <!-- Non-asymmetric (KTD-4): non-owner keeps direct wishes tab; owner goes through finance hub -->
    <van-tabbar-item v-if="!isOwner" name="wishes" icon="star-o">{{ t('nav.wishes') }}</van-tabbar-item>
    <van-tabbar-item name="finance" icon="balance-o">{{ t('nav.finance') }}</van-tabbar-item>
    <van-tabbar-item name="ai" :aria-label="t('settings.aiAssistant')">
      <template #icon="{ active: isActive }">
        <AIBrainIcon :active="isActive" />
      </template>
    </van-tabbar-item>
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

const activeTab = computed(() => {
  const path = route.path
  if (path === '/ai' || path.startsWith('/ai/')) return 'ai'
  if (path === '/settings' || path.startsWith('/settings/')) return 'settings'
  if (path === '/family' || path.startsWith('/family/')) return 'settings'
  if (path === '/baby' || path.startsWith('/baby/')) return 'baby'
  if (path.startsWith('/blind-box/')) return 'baby'
  if (path === '/chore-approvals') return 'baby'
  // KTD-2: finance hub covers assets/liabilities/wishes groups (path-prefix match,
  // covers all sub-routes incl. params). Owner has no wishes tab → /wishes* also maps
  // to finance. Non-owner keeps a direct wishes tab → /wishes* highlights wishes.
  if (path.startsWith('/assets') || path.startsWith('/liabilities')) return 'finance'
  if (path.startsWith('/finance')) return 'finance'
  if (path.startsWith('/wishes')) return isOwner.value ? 'finance' : 'wishes'
  return 'dashboard'
})

const tabToRoute: Record<string, string> = {
  dashboard: '/',
  wishes: '/wishes',
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
