<template>
  <div class="auth-page">
    <div class="child-avatar" :style="{ backgroundColor: avatarColor }">
      {{ (displayName ?? '?').charAt(0) }}
    </div>
    <p class="child-name">{{ displayName }}</p>

    <!-- WebAuthn mode -->
    <div v-if="authMode === 'webauthn'" class="webauthn-mode">
      <p class="instruction">使用面容或指纹解锁</p>
      <van-button
        round
        type="primary"
        size="large"
        :loading="loading"
        @click="attemptWebAuthn"
      >
        {{ loading ? '验证中...' : '🔓 解锁' }}
      </van-button>
      <van-button plain size="small" class="switch-btn" @click="switchToPin">
        使用图形密码
      </van-button>
    </div>

    <!-- PIN mode -->
    <div v-else class="pin-mode">
      <div class="pin-display" :class="{ shake: shaking }">
        <span
          v-for="i in 4"
          :key="i"
          class="pin-slot"
          :class="{ filled: pin.length >= i }"
        ></span>
      </div>

      <p v-if="childAuthStore.isLocked" class="lock-message">
        {{ childAuthStore.lockMessage ? t(`errors.${childAuthStore.lockMessage}`) : '' }}
      </p>
      <p v-else-if="childAuthStore.loginError" class="error-message">
        {{ childAuthStore.loginError ? t(`errors.${childAuthStore.loginError}`) : '' }}
      </p>

      <div class="emoji-grid">
        <button
          v-for="emoji in EMOJIS"
          :key="emoji"
          class="emoji-btn"
          :disabled="childAuthStore.isLocked || pin.length >= 4"
          @click="addEmoji(emoji)"
        >
          {{ emoji }}
        </button>
      </div>

      <div class="pin-actions">
        <van-button plain style="min-height:56px;min-width:80px" @click="deleteEmoji">删除</van-button>
        <van-button plain style="min-height:56px;min-width:80px" @click="clearPin">清除</van-button>
      </div>

      <van-button
        v-if="webAuthnAvailable"
        plain
        size="small"
        class="switch-btn"
        @click="switchToWebAuthn"
      >
        使用面容/指纹
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useChildAuthStore } from '@numina/auth'
import type { ChildUser } from '@/types'
import { checkWebAuthnSupport, authenticatePasskey } from '@/utils/webauthn'
import { getAuthenticationOptions, authenticateWithPasskey } from '@/api/webauthn'
import { setUser } from '@numina/auth'
import axios from 'axios'

const { t } = useI18n()

const EMOJIS = ['🐱', '🐶', '🐸', '🦊', '🐼', '🐨', '🦁', '🐯', '🌟', '🌈', '🍎', '🎈']

const route = useRoute()
const router = useRouter()
const childAuthStore = useChildAuthStore()

const childId = route.query.childId as string
const username = route.query.username as string  // 新增：username 方式
const displayName = route.query.displayName as string
const avatarColor = route.query.avatarColor as string

const authMode = ref<'webauthn' | 'pin'>('pin')
const loading = ref(false)
const pin = ref<string[]>([])
const shaking = ref(false)
const webAuthnAvailable = ref(false)

onMounted(async () => {
  const support = checkWebAuthnSupport()
  if (!support.supported) return

  webAuthnAvailable.value = true

  // Check if child has a registered passkey by requesting auth options
  try {
    await getAuthenticationOptions(childId)
    // No error means passkey exists — use WebAuthn mode
    authMode.value = 'webauthn'
  } catch {
    // No passkey registered — stay in PIN mode
  }
})

async function attemptWebAuthn() {
  loading.value = true
  try {
    const optionsResponse = await getAuthenticationOptions(childId)
    const { options, challenge } = optionsResponse

    const credential = await authenticatePasskey(options)
    await authenticateWithPasskey(childId, credential, challenge)

    setUser({
      id: childId,
      display_name: displayName,
      avatar_color: avatarColor,
      role: 'child',
    })

    showToast(t('toast.loginSuccess'))
    router.push('/child/')
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'NotAllowedError') {
      // User cancelled — don't show error
    } else if (axios.isAxiosError(err) && err.response?.status === 400) {
      showToast(t('toast.noPasskey'))
      authMode.value = 'pin'
    } else {
      showToast(t('toast.verifyFailed'))
    }
  } finally {
    loading.value = false
  }
}

function switchToPin() {
  authMode.value = 'pin'
}

function switchToWebAuthn() {
  authMode.value = 'webauthn'
}

function addEmoji(emoji: string) {
  if (pin.value.length < 4) {
    pin.value.push(emoji)
  }
}

function deleteEmoji() {
  pin.value.pop()
}

function clearPin() {
  pin.value = []
  childAuthStore.clearLoginError()
}

watch(
  () => pin.value.length,
  async (len) => {
    if (len === 4) {
      const selectedChild: ChildUser = {
        id: childId,
        username: username,  // 新增：传递 username
        display_name: displayName,
        avatar_color: avatarColor,
        is_active: true,
      }
      try {
        await childAuthStore.childLogin(selectedChild, [...pin.value])
        router.push('/child/')
      } catch {
        shaking.value = true
        pin.value = []
        setTimeout(() => {
          shaking.value = false
        }, 600)
      }
    }
  },
)
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 16px 24px;
  background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
}

.child-avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 12px;
}

.child-name {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 24px;
  color: #333;
}

/* WebAuthn mode */
.webauthn-mode {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.instruction {
  font-size: 16px;
  color: #666;
  margin: 0;
}

/* PIN mode */
.pin-mode {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.pin-display {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.pin-slot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid #999;
  background: transparent;
  transition: background 0.15s;
}

.pin-slot.filled {
  background: #333;
  border-color: #333;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-8px); }
  40% { transform: translateX(8px); }
  60% { transform: translateX(-6px); }
  80% { transform: translateX(6px); }
}

.shake {
  animation: shake 0.5s ease;
}

.lock-message,
.error-message {
  color: #e74c3c;
  font-size: 14px;
  margin: 0 0 16px;
}

.emoji-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
  width: 100%;
  max-width: 320px;
}

.emoji-btn {
  font-size: 28px;
  min-height: 56px;
  min-width: 56px;
  border: none;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  transition: transform 0.1s, opacity 0.1s;
}

.emoji-btn:active {
  transform: scale(0.92);
}

.emoji-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.pin-actions {
  display: flex;
  gap: 16px;
}

.switch-btn {
  margin-top: 16px;
}
</style>
