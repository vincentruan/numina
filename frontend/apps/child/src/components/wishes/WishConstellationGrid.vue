<template>
  <div v-if="wishes.length > 0" class="wish-constellation">
    <p class="constellation-headline">{{ headlineText }}</p>
    <div class="constellation-grid">
      <WishConstellationCard
        v-for="wish in wishes"
        :key="wish.id"
        :wish="wish"
        :tint="tintMap.get(wish.id) || 'gray'"
        :days-estimate-value="daysEstimateMap.get(wish.id) ?? null"
        :progress="wish.progress ?? 0"
        :peek-after-progress="peekActiveWishId && wish.id !== peekActiveWishId ? (deltaMap.get(wish.id)?.after_progress ?? null) : null"
        :days-added="peekActiveWishId && wish.id !== peekActiveWishId ? (deltaMap.get(wish.id)?.days_added ?? 0) : 0"
        :is-pressed="peekActiveWishId === wish.id"
        :reduced-motion="reducedMotion"
        @tap="onTap"
        @peek-start="onPeekStart"
        @peek-end="onPeekEnd"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ChildWish, ChildWishStats } from '@/api/childWishes'
import type { ReachabilityTint, SpendDelta } from '@numina/math'
import WishConstellationCard from './WishConstellationCard.vue'

const props = defineProps<{
  wishes: ChildWish[]
  stats: ChildWishStats | null
  daysEstimateMap: Map<string, number | null>
  tintMap: Map<string, ReachabilityTint>
  peekActiveWishId?: string | null
  peekDeltas?: SpendDelta[]
  reducedMotion?: boolean
}>()

const emit = defineEmits<{
  tap: [wishId: string]
  'peek-start': [wishId: string]
  'peek-end': [wishId: string]
}>()

const { t } = useI18n()

const deltaMap = computed(() => {
  const map = new Map<string, SpendDelta>()
  for (const d of props.peekDeltas ?? []) map.set(d.wish_id, d)
  return map
})

const greenCount = computed(() => {
  let k = 0
  for (const w of props.wishes) {
    if (props.tintMap.get(w.id) === 'green') k++
  }
  return k
})

const minDaysAcrossUncovered = computed<number | null>(() => {
  let min: number | null = null
  for (const w of props.wishes) {
    if (props.tintMap.get(w.id) === 'green') continue
    const d = props.daysEstimateMap.get(w.id)
    if (d == null) continue
    if (min === null || d < min) min = d
  }
  return min
})

const headlineText = computed(() => {
  const k = greenCount.value
  const n = props.wishes.length
  if (k > 0) return t('wishes.constellation.headline', { k, n })
  const d = minDaysAcrossUncovered.value
  if (d === null) return t('wishes.constellation.headlineZeroNoEstimate')
  return t('wishes.constellation.headlineZero', { d })
})

function onTap(wishId: string) {
  emit('tap', wishId)
}
function onPeekStart(wishId: string) {
  emit('peek-start', wishId)
}
function onPeekEnd(wishId: string) {
  emit('peek-end', wishId)
}
</script>

<style scoped>
.wish-constellation {
  margin-bottom: var(--space-lg);
}

.constellation-headline {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 12px;
  text-align: center;
}

.constellation-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

@media (max-width: 359px) {
  .constellation-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 768px) {
  .constellation-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
</style>
