<template>
  <div class="coin-slider">
    <van-slider
      v-model="internalValue"
      :min="1"
      :max="10"
      :step="1"
      bar-height="6px"
      active-color="var(--van-primary-color)"
      inactive-color="#e5e5e5"
      @update:model-value="onSliderChange"
    >
      <template #button>
        <component :is="coinComponent" :size="28" />
      </template>
    </van-slider>
    <!-- Scale marks -->
    <div class="scale-marks">
      <span>1</span>
      <span>5</span>
      <span>10</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import SilverCoin from './SilverCoin.vue'
import GoldenCoin from './GoldenCoin.vue'

const props = withDefaults(
  defineProps<{
    modelValue?: number
    coinType?: 'silver' | 'gold'
  }>(),
  {
    modelValue: 10,
    coinType: 'silver',
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: number): void
}>()

const internalValue = ref(props.modelValue)

watch(() => props.modelValue, (val) => {
  internalValue.value = val
})

const coinComponent = computed(() => {
  return props.coinType === 'silver' ? SilverCoin : GoldenCoin
})

function onSliderChange(val: number) {
  emit('update:modelValue', val)
}
</script>

<style scoped>
.coin-slider {
  padding: 4px 0;
}

.scale-marks {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  padding: 0 2px;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
