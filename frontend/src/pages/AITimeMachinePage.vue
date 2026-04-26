<template>
  <div class="time-machine-page">
    <van-nav-bar :title="t('timeMachine.title')" left-arrow @click-left="$router.back()" />
    <van-tabs v-model:active="activeTab" animated swipeable>
      <van-tab :title="t('timeMachine.whatif')">
        <WhatIfSimulator />
      </van-tab>
      <van-tab :title="t('timeMachine.projection')">
        <ProjectionChart />
      </van-tab>
      <van-tab :title="t('timeMachine.purchasingPower')">
        <PurchasingPowerCalc />
      </van-tab>
    </van-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import WhatIfSimulator from '@/components/ai/WhatIfSimulator.vue'
import ProjectionChart from '@/components/ai/ProjectionChart.vue'
import PurchasingPowerCalc from '@/components/ai/PurchasingPowerCalc.vue'

const { t } = useI18n()
const activeTab = ref(0)
</script>

<style scoped>
.time-machine-page {
  min-height: 100vh;
  background: var(--van-background);
}
</style>
