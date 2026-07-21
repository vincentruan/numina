<template>
  <div class="main-layout">
    <div v-if="!isOnline" class="offline-banner" role="alert" aria-live="assertive">
      {{ t('toast.networkError') }}
    </div>
    <router-view v-slot="{ Component, route }">
      <Transition name="page-fade" mode="out-in">
        <KeepAlive :include="cachedTabs">
          <component :is="Component" :key="route.path" />
        </KeepAlive>
      </Transition>
    </router-view>
    <AppTabBar />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppTabBar from '@/components/common/AppTabBar.vue'
import { useFamilyStore } from '@/stores/family'
import { useNetwork } from '@/composables/useNetwork'

const { t } = useI18n()
const familyStore = useFamilyStore()
const { isOnline } = useNetwork()

const cachedTabs = ref<string[]>([
  'Dashboard',
  'AssetList',
  'WishList',
  'LiabilityList',
  'FinanceHub',
  'AIHub',
  'Baby',
  'Settings',
])

onMounted(() => {
  if (!familyStore.family) {
    familyStore.fetchFamily()
  }
})
</script>

<style scoped>
.main-layout {
  min-height: 100vh;
  padding-bottom: calc(50px + env(safe-area-inset-bottom));
  background-color: var(--bg-secondary);
}

.offline-banner {
  position: sticky;
  top: 0;
  z-index: 9999;
  background: #ff3b30;
  color: #fff;
  text-align: center;
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 500;
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.15s ease;
}

.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}
</style>
