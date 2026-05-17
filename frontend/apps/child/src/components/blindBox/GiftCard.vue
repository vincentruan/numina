<template>
  <div
    class="gift-card"
    :class="{ surprise: gift.is_surprise, bonus: gift.is_bonus }"
    role="article"
    :aria-label="`${gift.gift_emoji ?? '🎁'} ${gift.gift_name}，${gift.is_surprise ? t('blindBox.surpriseAriaPrefix') : ''}${statusText}`"
  >
    <div class="gift-card-left">
      <span class="gift-emoji" aria-hidden="true">{{ gift.gift_emoji ?? '🎁' }}</span>
    </div>
    <div class="gift-card-body">
      <div class="gift-card-name">{{ gift.gift_name }}</div>
      <div class="gift-card-meta">
        <span class="coins-spent">{{ t('blindBox.coinsSpent', { coins: gift.coins_spent }) }}</span>
        <span v-if="gift.is_surprise" class="badge surprise-badge" aria-hidden="true">{{ t('blindBox.surpriseLabel') }}</span>
        <span v-if="gift.is_bonus" class="badge bonus-badge" aria-hidden="true">{{ t('blindBox.bonusLabel') }}</span>
      </div>
      <div class="gift-card-date">{{ formatDate(gift.draw_at) }}</div>
    </div>
    <div class="gift-card-status">
      <van-tag :type="gift.status === 'fulfilled' ? 'success' : 'warning'" size="medium">
        {{ statusText }}
      </van-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { BlindBoxDraw } from '@/types/blindBox'

const { t, locale } = useI18n()
const props = defineProps<{ gift: BlindBoxDraw }>()

const statusText = computed(() =>
  props.gift.status === 'fulfilled' ? t('blindBox.statusFulfilled') : t('blindBox.statusPending'),
)

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString(locale.value, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style scoped>
.gift-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--van-background-2);
  border-radius: 12px;
  padding: 12px 14px;
  border-left: 4px solid var(--van-primary-color);
}
.gift-card.surprise {
  border-left-color: var(--color-badge-surprise-border);
  background: linear-gradient(135deg, var(--color-badge-surprise-bg), var(--van-background-2));
}
.gift-card.bonus {
  border-left-color: var(--color-badge-bonus-border);
}
.gift-emoji {
  font-size: 32px;
}
.gift-card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.gift-card-name {
  font-size: 15px;
  font-weight: 600;
}
.gift-card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
}
.coins-spent {
  font-size: 12px;
  color: var(--van-text-color-2);
}
.badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 10px;
}
.surprise-badge {
  background: var(--color-badge-surprise-bg);
  color: var(--color-badge-surprise-text);
}
.bonus-badge {
  background: var(--color-badge-bonus-bg);
  color: var(--color-badge-bonus-text);
}
.gift-card-date {
  font-size: 11px;
  color: var(--van-text-color-3);
}
</style>
