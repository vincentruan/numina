<template>
  <div class="trusted-device-wrapper">
    <!-- Tappable card -->
    <div
      class="trusted-device-card"
      role="button"
      tabindex="0"
      aria-label="`以 ${displayName} 身份登录`"
      @click="emit('confirm')"
      @keydown.enter="emit('confirm')"
      @keydown.space.prevent="emit('confirm')"
    >
      <!-- Loading overlay -->
      <div v-if="loading" class="card-loading-overlay" aria-hidden="true">
        <div class="card-spinner" />
      </div>

      <!-- Avatar -->
      <div
        class="device-avatar"
        :style="{ background: avatarColor }"
        aria-hidden="true"
      >
        {{ displayName.charAt(0) }}
      </div>

      <!-- Display name -->
      <p class="device-name">{{ displayName }}</p>

      <!-- Tap hint -->
      <p class="device-hint">点击登录</p>
    </div>

    <!-- Switch account link -->
    <button
      class="switch-account-btn"
      type="button"
      :disabled="loading"
      @click="emit('switchAccount')"
    >
      切换账户
    </button>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  displayName: string
  avatarColor: string
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'switchAccount'): void
}>()
</script>

<style scoped>
.trusted-device-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

/* Card */
.trusted-device-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 32px 40px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 16px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s ease, transform 0.15s ease;
  min-width: 200px;
  overflow: hidden;
}

.trusted-device-card:hover {
  background: rgba(255, 255, 255, 0.1);
}

.trusted-device-card:active {
  transform: scale(0.97);
  background: rgba(255, 255, 255, 0.14);
}

/* Loading overlay */
.card-loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
  border-radius: 16px;
  z-index: 1;
}

.card-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: card-spin 0.7s linear infinite;
}

@keyframes card-spin {
  to { transform: rotate(360deg); }
}

/* Avatar */
.device-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: 600;
  color: #fff;
  text-transform: uppercase;
  flex-shrink: 0;
}

/* Name */
.device-name {
  margin: 0;
  font-size: 18px;
  font-weight: 500;
  color: #fff;
  letter-spacing: -0.01em;
}

/* Hint */
.device-hint {
  margin: 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
}

/* Switch account */
.switch-account-btn {
  background: none;
  border: none;
  padding: 4px 8px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  transition: color 0.15s;
}

.switch-account-btn:hover {
  color: rgba(255, 255, 255, 0.9);
}

.switch-account-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Light theme overrides */
:global(.theme-light) .trusted-device-card {
  background: rgba(0, 0, 0, 0.04);
  border-color: rgba(0, 0, 0, 0.1);
}

:global(.theme-light) .trusted-device-card:hover {
  background: rgba(0, 0, 0, 0.07);
}

:global(.theme-light) .trusted-device-card:active {
  background: rgba(0, 0, 0, 0.1);
}

:global(.theme-light) .device-name {
  color: #1a1a2e;
}

:global(.theme-light) .device-hint {
  color: rgba(0, 0, 0, 0.4);
}

:global(.theme-light) .switch-account-btn {
  color: rgba(0, 0, 0, 0.5);
}

:global(.theme-light) .switch-account-btn:hover {
  color: rgba(0, 0, 0, 0.8);
}
</style>
