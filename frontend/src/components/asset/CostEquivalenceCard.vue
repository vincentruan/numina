<template>
  <van-cell-group inset title="成本等价换算">
    <van-loading v-if="loading" class="card-loading" />
    <template v-else-if="result">
      <van-cell title="持有天数" :value="result.held_days != null ? `${result.held_days} 天` : '--'" />
      <van-cell title="日均成本" :value="result.daily_cost != null ? `¥${result.daily_cost.toFixed(2)}` : '--'" />
      <van-cell
        title="时间成本（按时薪 ¥50/小时）"
        :value="result.time_cost_hours != null ? `${result.time_cost_hours.toFixed(1)} 小时` : '--'"
      />
      <van-cell
        title="机会成本（按年化 5%，10年）"
        :value="result.opportunity_cost != null ? `¥${result.opportunity_cost.toLocaleString()}` : '--'"
      />
    </template>
    <van-empty v-else description="暂无数据" />
  </van-cell-group>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getCostEquivalence, type CostEquivalenceResult } from '@/api/assetsAnalysis'

const props = defineProps<{ assetId: number }>()

const loading = ref(false)
const result = ref<CostEquivalenceResult | null>(null)

onMounted(async () => {
  loading.value = true
  try {
    result.value = await getCostEquivalence(props.assetId)
  } catch {
    // non-critical, show empty state
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.card-loading {
  display: flex;
  justify-content: center;
  padding: 16px;
}
</style>
