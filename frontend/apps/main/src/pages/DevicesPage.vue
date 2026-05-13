<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast, showConfirmDialog } from 'vant'
import {
  listDevices,
  revokeDevice,
  revokeAllDevices,
  listFamilyDevices,
  type DeviceSession,
  type FamilyDevice,
} from '@/api/device'
import { useAuthStore } from '@/stores/auth'
import { clearAuth } from '@numina/auth'
import { useRouter } from 'vue-router'

const { t } = useI18n()
const authStore = useAuthStore()
const router = useRouter()

const activeTab = ref<'my' | 'family'>('my')
const isAdminOrOwner = computed(() => authStore.user?.role === 'owner')

// My devices
const devices = ref<DeviceSession[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await listDevices()
    devices.value = res.data
  } finally {
    loading.value = false
  }
}

async function handleRevoke(device: DeviceSession) {
  const confirmMsg = device.is_current ? t('device.revokeThis') : `${t('device.revoke')} ${device.device_name}？`
  try {
    await showConfirmDialog({ message: `⚠️ ${confirmMsg}` })
  } catch {
    return
  }
  await revokeDevice(device.id)
  showToast(t('toast.deviceRevokeSuccess'))
  if (device.is_current) {
    authStore.logout({ onLogout: () => router.push('/login') })
  } else {
    await load()
  }
}

async function handleRevokeAll() {
  try {
    await showConfirmDialog({ message: `⚠️ ${t('device.revokeAll')}？` })
  } catch {
    return
  }
  await revokeAllDevices()
  showToast(t('toast.deviceRevokeAllSuccess'))
  // Backend already cleared auth cookies; just clean local state and redirect
  authStore.user = null
  clearAuth()
  router.push('/login')
}

// Family devices
const familyDevices = ref<FamilyDevice[]>([])
const familyLoading = ref(false)
const familyLoaded = ref(false)

async function loadFamily() {
  if (familyLoaded.value) return
  familyLoading.value = true
  try {
    familyDevices.value = await listFamilyDevices()
    familyLoaded.value = true
  } finally {
    familyLoading.value = false
  }
}

// Group family devices by display_name
const familyGroups = computed(() => {
  const groups: Record<string, { display_name: string; avatar_color: string; devices: FamilyDevice[] }> = {}
  for (const d of familyDevices.value) {
    if (!groups[d.display_name]) {
      groups[d.display_name] = { display_name: d.display_name, avatar_color: d.avatar_color, devices: [] }
    }
    groups[d.display_name].devices.push(d)
  }
  return Object.values(groups)
})

async function handleRevokeFamily(device: FamilyDevice) {
  try {
    await showConfirmDialog({ message: `⚠️ ${t('device.revoke')} ${device.device_name}？` })
  } catch {
    return
  }
  await revokeDevice(String(device.id))
  showToast(t('toast.deviceRevokeSuccess'))
  familyLoaded.value = false
  await loadFamily()
}

function onTabChange(tab: 'my' | 'family') {
  activeTab.value = tab
  if (tab === 'family') {
    loadFamily()
  }
}

function formatRelativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return t('settings.timeJustNow')
  if (hours < 24) return t('settings.timeHoursAgo', { hours })
  return t('settings.timeDaysAgo', { days: Math.floor(hours / 24) })
}

onMounted(load)
</script>

<template>
  <van-nav-bar :title="t('device.title')" left-arrow @click-left="router.back()" />

  <!-- Tab switcher — only show when owner/admin -->
  <div v-if="isAdminOrOwner" style="display: flex; border-bottom: 1px solid var(--van-border-color)">
    <button
      v-for="tab in [{ key: 'my', label: t('device.myDevices') }, { key: 'family', label: t('device.childDevices') }]"
      :key="tab.key"
      style="
        flex: 1;
        padding: 12px 0;
        border: none;
        background: none;
        font-size: 14px;
        cursor: pointer;
        border-bottom: 2px solid transparent;
        transition: color 0.2s, border-color 0.2s;
      "
      :style="
        activeTab === tab.key
          ? { color: 'var(--van-primary-color)', borderBottomColor: 'var(--van-primary-color)', fontWeight: '600' }
          : { color: 'var(--van-text-color-2)' }
      "
      @click="onTabChange(tab.key as 'my' | 'family')"
    >
      {{ tab.label }}
    </button>
  </div>

  <!-- My Devices tab -->
  <template v-if="activeTab === 'my'">
    <van-pull-refresh v-model="loading" @refresh="load">
      <van-list>
        <van-cell
          v-for="device in devices"
          :key="device.id"
          :title="device.device_name"
          :label="`${t('device.lastSeen')}: ${formatRelativeTime(device.last_seen_at)}`"
        >
          <template #right-icon>
            <div style="display: flex; align-items: center; gap: 8px">
              <van-tag v-if="device.is_current" type="primary">
                {{ t('device.currentDevice') }}
              </van-tag>
              <van-button size="small" type="danger" plain @click="handleRevoke(device)">
                {{ device.is_current ? t('device.revokeThis') : t('device.revoke') }}
              </van-button>
            </div>
          </template>
        </van-cell>
      </van-list>
    </van-pull-refresh>

    <div v-if="devices.length > 1" style="padding: 16px">
      <van-button block type="warning" plain @click="handleRevokeAll">
        {{ t('device.revokeAll') }}
      </van-button>
    </div>
  </template>

  <!-- Family Devices tab -->
  <template v-if="activeTab === 'family'">
    <van-loading v-if="familyLoading" style="display: flex; justify-content: center; padding: 32px" />

    <template v-else>
      <van-empty v-if="familyGroups.length === 0" :description="t('device.noFamilyDevices')" />

      <template v-for="group in familyGroups" :key="group.display_name">
        <!-- Section header with avatar -->
        <div style="display: flex; align-items: center; gap: 8px; padding: 12px 16px 4px; background: var(--van-background)">
          <div
            style="
              width: 28px;
              height: 28px;
              border-radius: 50%;
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 13px;
              font-weight: 600;
              color: #fff;
              flex-shrink: 0;
            "
            :style="{ backgroundColor: group.avatar_color }"
          >
            {{ group.display_name.charAt(0) }}
          </div>
          <span style="font-size: 14px; font-weight: 600; color: var(--van-text-color)">{{ group.display_name }}</span>
        </div>

        <van-cell
          v-for="device in group.devices"
          :key="device.id"
          :title="device.device_name"
          :label="`${t('device.lastSeen')}: ${formatRelativeTime(device.last_seen_at)}`"
        >
          <template #right-icon>
            <van-button size="small" type="danger" plain @click="handleRevokeFamily(device)">
              {{ t('device.revokeChild') }}
            </van-button>
          </template>
        </van-cell>
      </template>
    </template>
  </template>
</template>
