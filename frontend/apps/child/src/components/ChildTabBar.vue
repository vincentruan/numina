<template>
  <div class="tab-bar-wrapper">
    <van-tabbar v-model="activeTab" @change="onTabChange">
      <van-tabbar-item name="home">
        <template #icon><van-icon name="wap-home-o" size="22" /></template>
        {{ t('nav.home') }}
      </van-tabbar-item>
      <van-tabbar-item name="wishes">
        <template #icon><van-icon name="star-o" size="22" /></template>
        {{ t('nav.wishes') }}
      </van-tabbar-item>
      <van-tabbar-item name="tasks">
        <template #icon><van-icon name="todo-list-o" size="22" /></template>
        {{ t('nav.tasks') }}
      </van-tabbar-item>
      <van-tabbar-item name="treasures">
        <template #icon><van-icon name="medal-o" size="22" /></template>
        {{ t('nav.treasures') }}
      </van-tabbar-item>
      <van-tabbar-item name="ledger">
        <template #icon><van-icon name="balance-list-o" size="22" /></template>
        {{ t('nav.ledger') }}
      </van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()

const TAB_ROUTES: Record<string, string> = {
  home: '/',
  wishes: '/wishes',
  tasks: '/tasks',
  treasures: '/treasures',
  ledger: '/ledger',
}

function routeToTab(path: string): string {
  if (path === '/') return 'home'
  const name = path.split('/')[1]
  return name in TAB_ROUTES ? name : 'home'
}

const activeTab = ref(routeToTab(route.path))

watch(() => route.path, (path) => {
  activeTab.value = routeToTab(path)
})

function onTabChange(name: string) {
  const target = TAB_ROUTES[name] ?? '/'
  // Always navigate — replace when already on the same route to avoid duplicate errors
  if (route.path === target) {
    router.replace(target)
  } else {
    router.push(target)
  }
}
</script>

<style scoped>
.tab-bar-wrapper {
  position: relative;
}

/* ── U4: Bouncy tab bar animation ── */
.tab-bar-wrapper :deep(.van-tabbar-item) {
  transition: transform 250ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.tab-bar-wrapper :deep(.van-tabbar-item--active) {
  transform: scale(1.1);
  animation: tab-bounce 250ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes tab-bounce {
  0%   { transform: scale(0.9); }
  60%  { transform: scale(1.1); }
  100% { transform: scale(1.1); }
}

/* Respect reduced-motion preference */
@media (prefers-reduced-motion: reduce) {
  .tab-bar-wrapper :deep(.van-tabbar-item) {
    transition: none;
  }
  .tab-bar-wrapper :deep(.van-tabbar-item--active) {
    animation: none;
    transform: none;
  }
}
</style>
