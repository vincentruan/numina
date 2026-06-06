<template>
  <van-nav-bar
    :title="activeTab === 'password' ? t('family.resetPasswordTitle', { name: childName }) : t('family.resetPinTitle2', { name: childName })"
    left-arrow
    @click-left="$router.back()"
  />

  <van-tabs v-model:active="activeTab" class="reset-tabs">
    <van-tab :title="t('family.resetPasswordTab')" name="password">
      <div class="tab-content">
        <van-cell-group inset>
          <van-field
            v-model="newPassword"
            :type="showPassword ? 'text' : 'password'"
            :label="t('family.newPasswordLabel')"
            :placeholder="t('family.newPasswordPlaceholder')"
          >
            <template #right-icon>
              <van-icon
                :name="showPassword ? 'eye-o' : 'closed-eye'"
                style="cursor: pointer"
                @click="showPassword = !showPassword"
              />
            </template>
          </van-field>
          <van-field
            v-model="confirmPassword"
            :type="showConfirmPassword ? 'text' : 'password'"
            :label="t('family.confirmNewPassword')"
            :placeholder="t('family.confirmNewPasswordPlaceholder')"
          >
            <template #right-icon>
              <van-icon
                :name="showConfirmPassword ? 'eye-o' : 'closed-eye'"
                style="cursor: pointer"
                @click="showConfirmPassword = !showConfirmPassword"
              />
            </template>
          </van-field>
        </van-cell-group>
        <div class="action-area">
          <van-button
            block
            type="primary"
            :loading="savingPassword"
            :disabled="!newPassword.trim() || newPassword !== confirmPassword"
            @click="doResetPassword"
          >{{ t('family.confirmResetPassword') }}</van-button>
        </div>
      </div>
    </van-tab>

    <van-tab :title="t('family.resetPinTab')" name="pin">
      <div class="tab-content">
        <p class="sheet-label">{{ t('family.selectNewPinEmojis') }}</p>
        <div class="emoji-picker">
          <button
            v-for="emoji in CHILD_EMOJIS"
            :key="emoji"
            class="emoji-pick-btn"
            :class="{ selected: newPin.includes(emoji) }"
            :disabled="newPin.length >= 4 && !newPin.includes(emoji)"
            @click="toggleNewPin(emoji)"
          >{{ emoji }}</button>
        </div>
        <p class="pin-preview">{{ newPin.length ? t('family.pinSelected', { emojis: newPin.join(' ') }) : t('family.pinSelectedEmpty') }}</p>
        <div class="action-area">
          <van-button
            block
            type="primary"
            :loading="savingPin"
            :disabled="newPin.length !== 4"
            @click="doResetPin"
          >{{ t('family.confirmResetPin') }}</van-button>
        </div>
      </div>
    </van-tab>
  </van-tabs>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { resetChildPin, resetChildPassword } from '@/api/children'

const { t } = useI18n()
const route = useRoute()

const childId = route.params.childId as string
const childName = route.query.name as string ?? ''

const activeTab = ref<'password' | 'pin'>('password')

const newPassword = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const showConfirmPassword = ref(false)
const savingPassword = ref(false)

const CHILD_EMOJIS = ['🐱', '🐶', '🐸', '🦊', '🐼', '🐨', '🦁', '🐯', '🌟', '🌈', '🍎', '🎈']
const newPin = ref<string[]>([])
const savingPin = ref(false)

function toggleNewPin(emoji: string) {
  const idx = newPin.value.indexOf(emoji)
  if (idx >= 0) {
    newPin.value.splice(idx, 1)
  } else if (newPin.value.length < 4) {
    newPin.value.push(emoji)
  }
}

async function doResetPassword() {
  if (!newPassword.value.trim()) return
  if (newPassword.value !== confirmPassword.value) {
    showToast(t('family.passwordMismatch'))
    return
  }
  savingPassword.value = true
  try {
    await resetChildPassword(childId, newPassword.value)
    showToast(t('toast.childPasswordReset'))
    newPassword.value = ''
    confirmPassword.value = ''
  } catch {
    showToast(t('toast.operationFailed'))
  } finally {
    savingPassword.value = false
  }
}

async function doResetPin() {
  if (newPin.value.length !== 4) return
  savingPin.value = true
  try {
    await resetChildPin(childId, [...newPin.value])
    showToast(t('toast.childPinReset'))
    newPin.value = []
  } catch {
    showToast(t('toast.operationFailed2'))
  } finally {
    savingPin.value = false
  }
}
</script>

<style scoped>
.reset-tabs {
  margin-top: 8px;
}

.tab-content {
  padding: 16px 0;
}

.sheet-label {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 16px 12px;
}

.emoji-picker {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
  margin: 0 16px 8px;
}

.emoji-pick-btn {
  font-size: 24px;
  padding: 6px;
  border: 2px solid transparent;
  border-radius: 8px;
  background: var(--bg-secondary);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.emoji-pick-btn.selected {
  border-color: var(--color-primary);
  background: var(--color-soft-stone);
}

.emoji-pick-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.pin-preview {
  font-size: 20px;
  text-align: center;
  margin: 4px 16px 0;
  letter-spacing: 4px;
}

.action-area {
  padding: 24px 16px 0;
}
</style>
