<template>
  <div class="debt-thresholds-page">
    <van-nav-bar
      :title="t('debtThresholds.title')"
      left-arrow
      @click-left="$router.back()"
    />

    <van-skeleton v-if="loading" :row="6" class="skeleton" />

    <template v-else>
      <van-cell-group inset :title="t('debtThresholds.groupTitle')" class="section">
        <van-cell :label="t('debtThresholds.groupDesc')" class="hint-cell" />
        <van-cell v-for="cat in categories" :key="cat.key">
          <template #title>
            <span>{{ t(`debtThresholds.${cat.key}`) }}</span>
            <span class="value">{{ form[cat.key] }}%</span>
          </template>
          <template #label>
            <div class="slider-track">
              <van-slider v-model="form[cat.key]" :min="1" :max="30" :step="1" @change="onSliderChange" />
            </div>
            <div class="slider-scale"><span>1%</span><span>15%</span><span>30%</span></div>
          </template>
        </van-cell>
      </van-cell-group>

      <div class="save-action">
        <van-button
          block
          type="primary"
          :loading="saving"
          @click="onSave"
        >
          {{ t('common.save') }}
        </van-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import http from '@/api/index'

defineOptions({ name: 'DebtThresholds' })

const { t } = useI18n()
const loading = ref(true)
const saving = ref(false)

const categories = [
  { key: 'credit_card' as const },
  { key: 'personal_loan' as const },
  { key: 'mortgage' as const },
  { key: 'other' as const },
]

const form = reactive({
  credit_card: 12,
  personal_loan: 10,
  mortgage: 6,
  other: 10,
})

let dirty = false

function onSliderChange() {
  dirty = true
}

async function load() {
  try {
    const res = await http.get<{ thresholds: Record<string, number> }>('/family/debt-thresholds')
    Object.assign(form, res.data.thresholds)
    dirty = false
  } catch {
    showFailToast(t('toast.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function onSave() {
  saving.value = true
  try {
    await http.put('/family/debt-thresholds', { thresholds: { ...form } })
    dirty = false
    showSuccessToast(t('toast.familyConfigSaved'))
  } catch {
    showFailToast(t('toast.operationFailed2'))
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.debt-thresholds-page {
  padding-bottom: 32px;
}
.section {
  margin-top: 12px;
}
.value {
  float: right;
  color: var(--van-text-color-2, #969799);
  font-size: 14px;
}
.hint-cell :deep(.van-cell__label) {
  color: var(--van-text-color-2, #969799);
  font-size: 12px;
}
.slider-track {
  padding: 8px 16px;
}
.slider-scale {
  display: flex;
  justify-content: space-between;
  padding: 0 16px;
  font-size: 11px;
  color: var(--van-text-color-3, #c8c9cc);
  margin-top: 2px;
}
.save-action {
  padding: 16px;
}
.skeleton {
  padding: 16px;
}
</style>
