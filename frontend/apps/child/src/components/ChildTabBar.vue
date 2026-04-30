<template>
  <div class="tab-bar-wrapper">
    <van-tabbar v-model="activeTab" @change="onTabChange">
      <van-tabbar-item name="home">
        <template #icon><span class="tab-icon">🏠</span></template>
        {{ t('nav.home') }}
      </van-tabbar-item>
      <van-tabbar-item name="wishes">
        <template #icon><span class="tab-icon">🌟</span></template>
        {{ t('nav.wishes') }}
      </van-tabbar-item>
      <van-tabbar-item name="tasks">
        <template #icon><span class="tab-icon">📋</span></template>
        {{ t('nav.tasks') }}
      </van-tabbar-item>
      <van-tabbar-item name="treasures">
        <template #icon><span class="tab-icon">🏆</span></template>
        {{ t('nav.treasures') }}
      </van-tabbar-item>
      <van-tabbar-item name="ledger">
        <template #icon><span class="tab-icon">💰</span></template>
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

.tab-icon {
  font-size: 20px;
  line-height: 1;
}
</style>
