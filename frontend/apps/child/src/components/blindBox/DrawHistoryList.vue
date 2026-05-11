<template>
  <div class="draw-history-list">
    <van-empty v-if="draws.length === 0" :description="t('blindBox.historyEmpty')" />
    <div v-else class="history-list" role="list" :aria-label="t('blindBox.historyAriaLabel')">
      <div v-for="draw in draws" :key="draw.id" role="listitem">
        <GiftCard :gift="draw" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import GiftCard from './GiftCard.vue'
import type { BlindBoxDraw } from '@/types/blindBox'

const { t } = useI18n()

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
