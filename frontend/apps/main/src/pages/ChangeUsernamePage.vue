<template>
  <div class="change-username-page">
    <PageHeader :title="t('changeUsername.title')" />

    <van-cell-group inset :title="t('changeUsername.sectionTitle')" class="section">
      <van-cell :title="t('changeUsername.currentUsername')" :value="authStore.user?.username ?? '-'" />
      <van-cell
        :title="t('changeUsername.remainingChanges')"
        :value="t('changeUsername.remainingCount', { count: remaining })"
        :value-class="{ 'value--warning': remaining <= 1 && remaining > 0, 'value--danger': remaining === 0 }"
      />
      <van-cell
        v-if="nextAvailableAt"
        :title="t('changeUsername.nextAvailableDate')"
        :value="nextAvailableAt"
      />
      <van-field
        v-model="newUsername"
        :label="t('changeUsername.newUsername')"
        :placeholder="t('changeUsername.newUsernamePlaceholder')"
        :rules="[{ required: true, message: t('changeUsername.usernameRequired') }]"
        :disabled="remaining === 0"
        autocomplete="username"
      />
    </van-cell-group>

    <div class="rule-hint">
      <van-icon name="info-o" />
      <span>{{ t('changeUsername.ruleDescription') }}</span>
    </div>

    <div class="action-area">
      <van-button
        round
        block
        type="primary"
        :loading="changing"
        :disabled="!canSubmit"
        @click="onChangeUsername"
      >
        {{ t('changeUsername.submit') }}
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import http from '@/api/index'
import PageHeader from '@/components/common/PageHeader.vue'
import { useAuthStore } from '@/stores/auth'
import { parseApiDate } from '@/utils/format'

const { t, locale } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const newUsername = ref('')
const changing = ref(false)

const remaining = computed(() => authStore.user?.username_changes_remaining ?? 3)
const limitReached = computed(() => remaining.value === 0)

const nextAvailableAt = computed(() => {
  const raw = authStore.user?.username_next_available_at
  if (!raw) return ''
  try {
    const date = parseApiDate(raw)
    return new Intl.DateTimeFormat(locale.value, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
  } catch {
    return raw
  }
})

const canSubmit = computed(() => {
  if (limitReached.value) return false
  const v = newUsername.value.trim().toLowerCase()
  return v.length >= 3 && v.length <= 50 && /^[a-z0-9_.-]+$/.test(v)
})

async function onChangeUsername() {
  const value = newUsername.value.trim().toLowerCase()
  if (!canSubmit.value) return

  try {
    await showConfirmDialog({ message: t('changeUsername.confirmChange', { name: value }) })
  } catch {
    return
  }

  changing.value = true
  try {
    await http.post('/auth/me/username', { new_username: value })
    await authStore.fetchMe()
    showSuccessToast(t('changeUsername.changeSuccess'))
    router.back()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { code?: string } } }
    const code = err.response?.data?.code
    if (code === 'AUTH_USERNAME_CHANGE_LIMIT') {
      showFailToast(t('changeUsername.limitReached', { date: nextAvailableAt.value }))
      // Refresh user data to update remaining count
      await authStore.fetchMe()
    } else if (code === 'AUTH_USERNAME_EXISTS') {
      showFailToast(t('changeUsername.usernameExists'))
    } else if (code && t(`errors.${code}`) !== `errors.${code}`) {
      showFailToast(t(`errors.${code}`))
    } else {
      showFailToast(t('changeUsername.changeFailed'))
    }
  } finally {
    changing.value = false
  }
}
</script>

<style scoped>
.change-username-page {
  min-height: 100vh;
  background: var(--van-background);
}

.section {
  margin-top: 12px;
}

.rule-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 20px 0;
  font-size: 12px;
  color: var(--text-secondary, #999);
}

.rule-hint .van-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.action-area {
  padding: 16px;
}

:deep(.value--warning) {
  color: var(--van-warning-color, #ff976a);
}

:deep(.value--danger) {
  color: var(--van-danger-color, #ee0a24);
}
</style>
