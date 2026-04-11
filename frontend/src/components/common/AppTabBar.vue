<template>
  <van-tabbar :model-value="activeTab" @change="onTabChange">
    <van-tabbar-item name="dashboard" icon="chart-trending-o">{{ t('nav.dashboard') }}</van-tabbar-item>
    <van-tabbar-item name="wishes" icon="star-o">{{ t('nav.wishes') }}</van-tabbar-item>
    <van-tabbar-item name="add" icon="add-o" aria-label="添加资产">
      <template #icon="{ active: isActive }">
        <div class="add-btn" :class="{ active: isActive }">
          <van-icon name="plus" size="24" />
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
}

function onTabChange(name: string | number) {
  if (name === 'add') {
    router.push('/assets/new')
    return
  }
  const target = tabToRoute[name as string]
  if (target && route.path !== target) {
    router.push(target)
  }
}
</script>

<style scoped>
.add-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--color-action-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: -10px;
  color: #fff;
  box-shadow: 0 2px 8px rgba(21, 101, 192, 0.4);
}
.add-btn.active {
  background: var(--color-action-primary-active);
}
</style>
