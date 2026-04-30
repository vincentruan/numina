<template>
  <div class="draw-animation" :class="{ animating }" role="status" :aria-live="animating ? 'polite' : 'off'">
    <div class="box-container" @click="!animating && $emit('draw')">
      <div class="box" :class="{ shake: animating, open: revealed }">
        <span class="box-emoji" aria-hidden="true">{{ revealed ? (gift?.gift_emoji ?? '🎁') : '📦' }}</span>
      </div>
      <div v-if="!animating && !revealed" class="tap-hint">{{ t('blindBox.tapHint') }}</div>
      <div v-if="animating" class="loading-hint">{{ t('blindBox.drawing') }}</div>
    </div>

    <transition name="reveal">
      <div
        v-if="revealed && gift"
        class="gift-reveal"
        role="alert"
        :aria-label="t('blindBox.giftRevealLabel', { name: gift.gift_name })"
      >
        <div class="gift-emoji-large" aria-hidden="true">{{ gift.gift_emoji ?? '🎁' }}</div>
        <div class="gift-name">{{ gift.gift_name }}</div>
        <div v-if="gift.is_surprise" class="surprise-badge">{{ t('blindBox.surpriseBadge') }}</div>
        <div v-if="gift.is_bonus" class="bonus-badge">{{ t('blindBox.bonusBadge') }}</div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { BlindBoxDraw } from '@/types/blindBox'

const { t } = useI18n()

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

/* Box — lavender feature card when closed, pink when open */
.box {
  width: 120px;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-xl);
  background: var(--color-brand-lavender);
  transition: transform 0.2s, background 0.3s;
}
.box:active { transform: scale(0.95); }
.box.shake { animation: shake 0.5s ease-in-out infinite; }
.box.open  { background: var(--color-brand-pink); }

.box-emoji { font-size: 52px; }

@keyframes shake {
  0%, 100% { transform: rotate(0deg); }
  25% { transform: rotate(-8deg); }
  75% { transform: rotate(8deg); }
}

.tap-hint, .loading-hint {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-muted-soft);
  font-weight: 500;
}

/* Gift reveal */
.gift-reveal {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
}
.gift-emoji-large { font-size: 64px; }
.gift-name {
  font-family: Inter, sans-serif;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-ink);
}

/* Badges — Clay brand colors */
.surprise-badge {
  background: var(--color-brand-pink);
  color: var(--color-on-primary);
  padding: 4px 14px;
  border-radius: var(--radius-pill);
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
}
.bonus-badge {
  background: var(--color-brand-mint);
  color: var(--color-ink);
  padding: 4px 14px;
  border-radius: var(--radius-pill);
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
}

.reveal-enter-active {
  animation: pop 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
@keyframes pop {
  from { transform: scale(0); opacity: 0; }
  to   { transform: scale(1); opacity: 1; }
}
</style>
