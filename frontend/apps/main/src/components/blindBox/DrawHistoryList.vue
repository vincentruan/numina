<template>
  <div class="draw-history-list">
    <van-empty v-if="draws.length === 0" description="暂无抽奖记录" />
    <div v-else class="history-list" role="list" aria-label="抽奖历史">
      <div v-for="draw in draws" :key="draw.id" role="listitem">
        <GiftCard :gift="draw" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import GiftCard from './GiftCard.vue'
import type { BlindBoxDraw } from '@/types/blindBox'

defineProps<{
  draws: BlindBoxDraw[]
}>()
</script>

<style scoped>
.draw-history-list {
  padding: 12px;
}
.history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
