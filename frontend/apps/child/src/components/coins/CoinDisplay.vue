<template>
  <span class="coin-display">
    <template v-if="displayTiers.gold > 0">
      <GoldenCoin :size="iconSize" />
      <span class="coin-count gold" :class="{ 'is-counting': activeTier === 'gold' }">{{ displayTiers.gold }}</span>
    </template>
    <template v-if="displayTiers.silver > 0">
      <SilverCoin :size="iconSize" />
      <span class="coin-count silver" :class="{ 'is-counting': activeTier === 'silver' }">{{ displayTiers.silver }}</span>
    </template>
    <template v-if="displayTiers.copper > 0 || (displayTiers.gold === 0 && displayTiers.silver === 0)">
      <CopperCoin :size="iconSize" />
      <span class="coin-count copper" :class="{ 'is-counting': activeTier === 'copper' }">{{ displayTiers.copper }}</span>
    </template>
  </span>
</template>

<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import { splitCoinTiers, type CoinTier } from '@/utils/coinTier'
import GoldenCoin from './GoldenCoin.vue'
import SilverCoin from './SilverCoin.vue'
import CopperCoin from './CopperCoin.vue'

const props = withDefaults(
  defineProps<{
    amount: number
    iconSize?: number
    copperToSilver?: number
    silverToGold?: number
    animateChanges?: boolean
  }>(),
  {
    iconSize: 20,
    copperToSilver: 10,
    silverToGold: 10,
    animateChanges: false,
  },
)

const staticTiers = computed(() => splitCoinTiers(props.amount, props.copperToSilver, props.silverToGold))

const animatedTiers = ref<CoinTier>({ gold: 0, silver: 0, copper: 0 })
const animating = ref(false)
const activeTier = ref<'gold' | 'silver' | 'copper' | null>(null)

const displayTiers = computed<CoinTier>(() => (animating.value ? animatedTiers.value : staticTiers.value))

let rafId: number | null = null
let timers: Array<ReturnType<typeof setTimeout>> = []

function clearAnimations(): void {
  if (rafId !== null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
  timers.forEach(clearTimeout)
  timers = []
}

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3)
}

function animateTier(
  tier: 'gold' | 'silver' | 'copper',
  fromVal: number,
  toVal: number,
  duration: number,
  delay: number,
): Promise<void> {
  return new Promise((resolve) => {
    const startTimer = setTimeout(() => {
      activeTier.value = tier
      const startedAt = performance.now()
      const tick = (now: number) => {
        const t = Math.min(1, (now - startedAt) / duration)
        const eased = easeOutCubic(t)
        const v = Math.round(fromVal + (toVal - fromVal) * eased)
        animatedTiers.value = { ...animatedTiers.value, [tier]: v }
        if (t < 1) {
          rafId = requestAnimationFrame(tick)
        } else {
          rafId = null
          if (activeTier.value === tier) activeTier.value = null
          resolve()
        }
      }
      rafId = requestAnimationFrame(tick)
    }, delay)
    timers.push(startTimer)
  })
}

async function runCascade(prev: CoinTier, next: CoinTier): Promise<void> {
  clearAnimations()
  animatedTiers.value = { ...prev }
  animating.value = true
  // copper 0–400ms, silver 400–900ms, gold 900–1500ms
  await Promise.all([
    animateTier('copper', prev.copper, next.copper, 400, 0),
    animateTier('silver', prev.silver, next.silver, 500, 400),
    animateTier('gold', prev.gold, next.gold, 600, 900),
  ])
  animating.value = false
  activeTier.value = null
}

watch(
  () => props.amount,
  (next, prevAmount) => {
    if (!props.animateChanges) return
    if (prevAmount === undefined || prevAmount === next) return
    const prev = splitCoinTiers(prevAmount, props.copperToSilver, props.silverToGold)
    const target = splitCoinTiers(next, props.copperToSilver, props.silverToGold)
    void runCascade(prev, target)
  },
)

onUnmounted(clearAnimations)
</script>

<style scoped>
.coin-display {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.coin-count {
  font-weight: 600;
  font-size: 0.9em;
  margin-right: 4px;
  display: inline-block;
  transform-origin: center;
  transition: transform 180ms cubic-bezier(0.175, 0.885, 0.32, 1.275),
              color 180ms ease-out,
              font-weight 100ms ease-out;
}
.coin-count.is-counting {
  font-weight: 700;
  transform: scale(1.35);
  color: var(--color-brand-ochre);
  text-shadow: 0 0 8px rgba(232, 185, 74, 0.55);
}
.coin-count.gold   { color: var(--color-coin-gold-text); }
.coin-count.silver { color: var(--color-coin-silver-text); }
.coin-count.copper { color: var(--color-coin-copper-text); }
.coin-count.is-counting.gold,
.coin-count.is-counting.silver,
.coin-count.is-counting.copper {
  color: var(--color-brand-ochre);
}
</style>
