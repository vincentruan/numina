<template>
  <span class="coin-display">
    <template v-if="tiers.gold > 0">
      <GoldenCoin :size="iconSize" />
      <span class="coin-count gold">{{ tiers.gold }}</span>
    </template>
    <template v-if="tiers.silver > 0">
      <SilverCoin :size="iconSize" />
      <span class="coin-count silver">{{ tiers.silver }}</span>
    </template>
    <template v-if="tiers.copper > 0 || (tiers.gold === 0 && tiers.silver === 0)">
      <CopperCoin :size="iconSize" />
      <span class="coin-count copper">{{ tiers.copper }}</span>
    </template>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { splitCoinTiers } from '@/utils/coinTier'
import GoldenCoin from './GoldenCoin.vue'
import SilverCoin from './SilverCoin.vue'
import CopperCoin from './CopperCoin.vue'

const props = withDefaults(
  defineProps<{
    amount: number
    iconSize?: number
    copperToSilver?: number
    silverToGold?: number
  }>(),
  {
    iconSize: 20,
    copperToSilver: 10,
    silverToGold: 10,
  },
)

const tiers = computed(() => splitCoinTiers(props.amount, props.copperToSilver, props.silverToGold))
</script>

<style scoped>
.coin-display {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.coin-count {
  font-weight: bold;
  font-size: 0.9em;
  margin-right: 4px;
}
.coin-count.gold {
  color: #b8860b;
}
.coin-count.silver {
  color: #808080;
}
.coin-count.copper {
  color: #8b4513;
}
</style>
