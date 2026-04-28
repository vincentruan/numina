<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast, showConfirmDialog } from 'vant'
import { listDevices, revokeDevice, revokeAllDevices, type DeviceSession } from '@/api/device'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const { t } = useI18n()
const authStore = useAuthStore()
const router = useRouter()

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
  authStore.logout({ onLogout: () => router.push('/login') })
}

function formatRelativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return '刚刚'
  if (hours < 24) return `${hours} 小时前`
  return `${Math.floor(hours / 24)} 天前`
}

onMounted(load)
</script>

<template>
  <van-nav-bar :title="t('device.title')" left-arrow @click-left="router.back()" />

  <van-pull-refresh v-model="loading" @refresh="load">
    <van-list>
      <van-cell
        v-for="device in devices"
        :key="device.id"
        :title="device.device_name"
        :label="`${t('device.lastSeen')}: ${formatRelativeTime(device.last_seen_at)}`"
      >
        <template #right-icon>
          <van-tag v-if="device.is_current" type="primary" style="margin-right: 8px">
            {{ t('device.currentDevice') }}
          </van-tag>
          <van-button size="small" type="danger" plain @click="handleRevoke(device)">
            {{ device.is_current ? t('device.revokeThis') : t('device.revoke') }}
          </van-button>
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
