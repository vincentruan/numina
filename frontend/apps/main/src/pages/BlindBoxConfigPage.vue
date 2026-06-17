<template>
  <div class="blind-box-config-page">
    <van-nav-bar :title="t('blindBox.configTitle')" left-arrow @click-left="$router.back()" />

    <template v-if="!loading && config">
      <van-cell-group inset :title="t('blindBox.basicSettings')">
        <van-cell :title="t('blindBox.enableFeature')" center>
          <template #right-icon>
            <van-switch v-model="form.enabled" @change="onSave" />
          </template>
        </van-cell>
      </van-cell-group>

      <van-cell-group inset :title="t('blindBox.drawProbGroup')">
        <van-cell :title="t('blindBox.baseDrawProb', { pct: Math.round((form.base_draw_prob ?? 0) * 100) })">
          <template #label>
            <van-slider
              v-model="form.base_draw_prob"
              :min="0"
              :max="1"
              :step="0.05"
              :aria-label="t('blindBox.baseDrawProb', { pct: Math.round((form.base_draw_prob ?? 0) * 100) })"
              @change="onSave"
            />
          </template>
        </van-cell>
        <van-cell :title="t('blindBox.specialDayProb', { pct: Math.round((form.special_day_prob ?? 0) * 100) })">
          <template #label>
            <van-slider
              v-model="form.special_day_prob"
              :min="0"
              :max="1"
              :step="0.05"
              :aria-label="t('blindBox.specialDayProb', { pct: Math.round((form.special_day_prob ?? 0) * 100) })"
              @change="onSave"
            />
          </template>
        </van-cell>
      </van-cell-group>

      <van-cell-group inset :title="t('blindBox.surpriseProbGroup')">
        <van-cell :title="t('blindBox.surpriseProbNormal', { pct: Math.round((form.surprise_prob_normal ?? 0) * 100) })">
          <template #label>
            <van-slider
              v-model="form.surprise_prob_normal"
              :min="0"
              :max="1"
              :step="0.05"
              :aria-label="t('blindBox.surpriseProbNormal', { pct: Math.round((form.surprise_prob_normal ?? 0) * 100) })"
              @change="onSave"
            />
          </template>
        </van-cell>
        <van-cell :title="t('blindBox.surpriseProbParentBday', { pct: Math.round((form.surprise_prob_parent_bday ?? 0) * 100) })">
          <template #label>
            <van-slider
              v-model="form.surprise_prob_parent_bday"
              :min="0"
              :max="1"
              :step="0.05"
              :aria-label="t('blindBox.surpriseProbParentBday', { pct: Math.round((form.surprise_prob_parent_bday ?? 0) * 100) })"
              @change="onSave"
            />
          </template>
        </van-cell>
        <van-cell :title="t('blindBox.surpriseProbSiblingBday', { pct: Math.round((form.surprise_prob_sibling_bday ?? 0) * 100) })">
          <template #label>
            <van-slider
              v-model="form.surprise_prob_sibling_bday"
              :min="0"
              :max="1"
              :step="0.05"
              :aria-label="t('blindBox.surpriseProbSiblingBday', { pct: Math.round((form.surprise_prob_sibling_bday ?? 0) * 100) })"
              @change="onSave"
            />
          </template>
        </van-cell>
      </van-cell-group>

      <van-cell-group inset :title="t('blindBox.weightGroup')">
        <van-field
          v-model.number="form.weight_scale"
          :label="t('blindBox.weightScaleLabel')"
          type="number"
          :placeholder="t('blindBox.weightScalePlaceholder')"
          @blur="onSave"
        />
        <van-field
          v-model.number="form.surprise_threshold_coins"
          :label="t('blindBox.surpriseThresholdLabel')"
          type="number"
          :placeholder="t('blindBox.surpriseThresholdPlaceholder')"
          @blur="onSave"
        />
      </van-cell-group>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, watch } from 'vue'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useBlindBoxStore } from '@/stores/blindBox'
import { storeToRefs } from 'pinia'
import { usePageLoading } from '@/composables/usePageLoading'

const { t } = useI18n()
const store = useBlindBoxStore()
const { config, loading } = storeToRefs(store)
const { increment, decrement } = usePageLoading()

const form = reactive({
  enabled: true,
  base_draw_prob: 0.3,
  special_day_prob: 0.8,
  weight_scale: 2.0,
  surprise_threshold_coins: 200,
  surprise_prob_normal: 0.05,
  surprise_prob_parent_bday: 0.6,
  surprise_prob_sibling_bday: 0.5,
})

onMounted(async () => {
  increment()
  try {
    await store.fetchConfig()
    if (config.value) Object.assign(form, config.value)
  } finally {
    decrement()
  }
})

watch(config, (val) => {
  if (val) Object.assign(form, val)
})

let _saveTimer: ReturnType<typeof setTimeout> | null = null

function onSave() {
  if (_saveTimer) clearTimeout(_saveTimer)
  _saveTimer = setTimeout(async () => {
    await store.updateConfig({ ...form })
    showSuccessToast(t('toast.saveSuccess'))
  }, 600)
}
</script>

<style scoped>
.blind-box-config-page {
  min-height: 100vh;
  background: var(--van-background);
}
</style>
