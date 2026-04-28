<template>
  <div
    class="gift-card"
    :class="{ surprise: gift.is_surprise, bonus: gift.is_bonus }"
    role="article"
    :aria-label="`${gift.gift_emoji ?? '🎁'} ${gift.gift_name}，${gift.is_surprise ? '超预期惊喜，' : ''}${statusText}`"
  >
    <div class="gift-card-left">
      <span class="gift-emoji" aria-hidden="true">{{ gift.gift_emoji ?? '🎁' }}</span>
    </div>
    <div class="gift-card-body">
      <div class="gift-card-name">{{ gift.gift_name }}</div>
      <div class="gift-card-meta">
        <span class="coins-spent">花费 {{ gift.coins_spent }} 金币</span>
        <span v-if="gift.is_surprise" class="badge surprise-badge" aria-hidden="true">✨ 惊喜</span>
        <span v-if="gift.is_bonus" class="badge bonus-badge" aria-hidden="true">🎀 免费</span>
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
import type { BlindBoxDraw } from '@/types/blindBox'

const props = defineProps<{ gift: BlindBoxDraw }>()

const statusText = computed(() =>
  props.gift.status === 'fulfilled' ? '已兑现' : '待兑现',
)

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('zh-CN', {
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
  border-left-color: #f5576c;
  background: linear-gradient(135deg, #fff5f5, var(--van-background-2));
}
.gift-card.bonus {
  border-left-color: #4facfe;
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
  background: #ffeef0;
  color: #f5576c;
}
.bonus-badge {
  background: #e8f7ff;
  color: #4facfe;
}
.gift-card-date {
  font-size: 11px;
  color: var(--van-text-color-3);
}
</style>
