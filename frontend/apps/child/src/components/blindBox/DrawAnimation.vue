<template>
  <div class="draw-animation" :class="{ animating }" role="status" :aria-live="animating ? 'polite' : 'off'">
    <div class="box-container" @click="!animating && $emit('draw')">
      <div class="box" :class="{ shake: animating, open: revealed }">
        <span class="box-emoji" aria-hidden="true">{{ revealed ? (gift?.gift_emoji ?? '🎁') : '📦' }}</span>
      </div>
      <div v-if="!animating && !revealed" class="tap-hint">点击抽奖</div>
      <div v-if="animating" class="loading-hint">抽奖中...</div>
    </div>

    <transition name="reveal">
      <div v-if="revealed && gift" class="gift-reveal" role="alert" :aria-label="`恭喜！抽到了 ${gift.gift_name}`">
        <div class="gift-emoji-large" aria-hidden="true">{{ gift.gift_emoji ?? '🎁' }}</div>
        <div class="gift-name">{{ gift.gift_name }}</div>
        <div v-if="gift.is_surprise" class="surprise-badge" aria-label="超预期惊喜">✨ 超预期惊喜！</div>
        <div v-if="gift.is_bonus" class="bonus-badge" aria-label="免费抽奖">🎀 免费抽奖</div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import type { BlindBoxDraw } from '@/types/blindBox'

defineProps<{
  animating: boolean
  revealed: boolean
  gift: BlindBoxDraw | null
}>()

defineEmits<{
  draw: []
}>()
</script>

<style scoped>
.draw-animation {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 16px;
  gap: 20px;
}
.box-container {
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.box {
  width: 100px;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.4);
  transition: transform 0.2s;
}
.box:active {
  transform: scale(0.95);
}
.box-emoji {
  font-size: 48px;
}
.box.shake {
  animation: shake 0.5s ease-in-out infinite;
}
.box.open {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}
@keyframes shake {
  0%, 100% { transform: rotate(0deg); }
  25% { transform: rotate(-8deg); }
  75% { transform: rotate(8deg); }
}
.tap-hint, .loading-hint {
  font-size: 13px;
  color: var(--van-text-color-2);
}
.gift-reveal {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
}
.gift-emoji-large {
  font-size: 64px;
}
.gift-name {
  font-size: 20px;
  font-weight: 700;
}
.surprise-badge {
  background: linear-gradient(135deg, #f093fb, #f5576c);
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
}
.bonus-badge {
  background: linear-gradient(135deg, #4facfe, #00f2fe);
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
}
.reveal-enter-active {
  animation: pop 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
@keyframes pop {
  from { transform: scale(0); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
</style>
