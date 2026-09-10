<template>
  <div class="main-layout">
    <div v-if="!isOnline" class="offline-banner" role="alert" aria-live="assertive">
      {{ t('toast.networkError') }}
    </div>
    <router-view v-slot="{ Component }">
      <Transition>
        <KeepAlive :include="cachedTabs">
          <component :is="Component" />
        </KeepAlive>
      </Transition>
    </router-view>
    <AppTabBar />
    <Transition name="slide-up">
      <div v-if="canInstall" class="install-prompt" role="alert">
        <div class="install-prompt__content">
          <p class="install-prompt__text">{{ t('pwa.installPrompt') }}</p>
          <div class="install-prompt__actions">
            <van-button size="small" type="primary" @click="promptInstall">{{ t('pwa.install') }}</van-button>
            <van-button size="small" plain @click="dismissInstall">{{ t('pwa.dismiss') }}</van-button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppTabBar from '@/components/common/AppTabBar.vue'
import { useFamilyStore } from '@/stores/family'
import { useNetwork } from '@/composables/useNetwork'
import { useInstallPrompt } from '@/composables/useInstallPrompt'

const { t } = useI18n()
const familyStore = useFamilyStore()
const { isOnline } = useNetwork()
const { canInstall, promptInstall, dismissInstall } = useInstallPrompt()

const cachedTabs = ref<string[]>([
  'Dashboard',
  'FinanceHub',
  'AIHub',
  'Baby',
  'Family',
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

.install-prompt {
  position: fixed;
  bottom: calc(50px + env(safe-area-inset-bottom));
  left: 0;
  right: 0;
  z-index: 2000;
  background: var(--card-bg, #fff);
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.12);
  padding: 12px 16px;
}

.install-prompt__content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.install-prompt__text {
  margin: 0;
  font-size: 14px;
  color: var(--text-primary, #0a0a0a);
  flex: 1;
}

.install-prompt__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
}

</style>
