<template>
  <van-tabbar :model-value="activeTab" @change="onTabChange">
    <van-tabbar-item name="dashboard" icon="chart-trending-o">{{ t('nav.dashboard') }}</van-tabbar-item>
    <van-tabbar-item name="wishes" icon="star-o">{{ t('nav.wishes') }}</van-tabbar-item>
    <van-tabbar-item name="ai" aria-label="AI 智能助手">
      <template #icon="{ active: isActive }">
        <div class="ai-btn" :class="{ active: isActive }">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <!-- Brain outline -->
            <path d="M9.5 2a2.5 2.5 0 0 1 5 0"/>
            <path d="M9 2.5C6.5 3 4 5.5 4 9c0 1.5.5 2.8 1.3 3.8"/>
            <path d="M15 2.5C17.5 3 20 5.5 20 9c0 1.5-.5 2.8-1.3 3.8"/>
            <path d="M5.3 12.8C4.5 14 4 15.5 4 17a5 5 0 0 0 5 5h6a5 5 0 0 0 5-5c0-1.5-.5-3-1.3-4.2"/>
            <!-- Neural nodes -->
            <circle cx="12" cy="10" r="1.2" fill="currentColor" stroke="none"/>
            <circle cx="8.5" cy="13" r="1" fill="currentColor" stroke="none"/>
            <circle cx="15.5" cy="13" r="1" fill="currentColor" stroke="none"/>
            <circle cx="12" cy="16" r="1" fill="currentColor" stroke="none"/>
            <!-- Connections -->
            <line x1="12" y1="11.2" x2="8.5" y2="12"/>
            <line x1="12" y1="11.2" x2="15.5" y2="12"/>
            <line x1="8.5" y1="14" x2="12" y2="15"/>
            <line x1="15.5" y1="14" x2="12" y2="15"/>
          </svg>
        </div>
      </template>
      <span></span>
    </van-tabbar-item>
    <van-tabbar-item name="liabilities" icon="bill-o">{{ t('nav.liabilities') }}</van-tabbar-item>
    <van-tabbar-item name="stats" icon="bar-chart-o">{{ t('nav.stats') }}</van-tabbar-item>
    <van-tabbar-item name="settings" icon="setting-o">{{ t('nav.settings') }}</van-tabbar-item>
  </van-tabbar>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const router = useRouter()
const route = useRoute()

const routeToTab: Record<string, string> = {
  '/': 'dashboard',
  '/wishes': 'wishes',
  '/liabilities': 'liabilities',
  '/stats': 'stats',
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
  stats: '/stats',
  settings: '/settings',
  ai: '/ai',
}

function onTabChange(name: string | number) {
  const target = tabToRoute[name as string]
  if (target && route.path !== target) {
    router.push(target)
  }
}
</script>

<style scoped>
.ai-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1 0%, #7c3aed 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: -10px;
  color: #fff;
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.5);
  transition: box-shadow 0.2s ease;
}
.ai-btn.active {
  box-shadow: 0 2px 18px rgba(124, 58, 237, 0.7);
}
</style>
