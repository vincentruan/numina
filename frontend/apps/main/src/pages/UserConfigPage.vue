<template>
  <div class="user-config-page">
    <van-nav-bar
      :title="t('userConfig.title')"
      left-arrow
      @click-left="$router.back()"
    />

    <van-skeleton v-if="loading" :row="4" class="skeleton" />

    <template v-else>
      <!-- Dashboard Preferences -->
      <van-cell-group inset :title="t('userConfig.dashboardGroup')" class="section">
        <van-field
          :model-value="trendPeriodLabel"
          :label="t('userConfig.trendPeriod')"
          readonly
          is-link
          @click="showTrendPicker = true"
        />
      </van-cell-group>

      <!-- Activity Feed -->
      <van-cell-group inset :title="t('userConfig.activityGroup')" class="section">
        <van-cell>
          <template #title>
            <span>{{ t('userConfig.activityPageSize') }}</span>
            <span class="value">{{ form.activity_feed_page_size }} {{ t('userConfig.unitItems') }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('userConfig.activityPageSizeDesc') }}</span>
            <van-slider v-model="form.activity_feed_page_size" :min="5" :max="50" :step="5" @change="onSave" />
          </template>
        </van-cell>
      </van-cell-group>
    </template>

    <!-- Trend Period Picker -->
    <van-popup v-model:show="showTrendPicker" position="bottom" round>
      <van-picker
        :columns="trendPeriodColumns"
        @confirm="onTrendConfirm"
        @cancel="showTrendPicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { getUserConfig, updateUserConfig } from '@/api/config'

defineOptions({ name: 'UserConfig' })

const { t } = useI18n()
const loading = ref(true)
const showTrendPicker = ref(false)

const form = ref({
  dashboard_trend_period: 'month',
  activity_feed_page_size: 20,
})

const trendPeriodColumns = computed(() => [
  { text: t('userConfig.trendPeriodMonth'), value: 'month' },
  { text: t('userConfig.trendPeriodQuarter'), value: 'quarter' },
  { text: t('userConfig.trendPeriodYear'), value: 'year' },
])

const trendPeriodLabel = computed(() => {
  const map: Record<string, string> = {
    month: t('userConfig.trendPeriodMonth'),
    quarter: t('userConfig.trendPeriodQuarter'),
    year: t('userConfig.trendPeriodYear'),
  }
  return map[form.value.dashboard_trend_period] || ''
})

let saveTimer: ReturnType<typeof setTimeout> | null = null

function onSave() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    try {
      await updateUserConfig(form.value)
      showSuccessToast(t('toast.userConfigSaved'))
    } catch {
      showFailToast(t('toast.operationFailed2'))
    }
  }, 600)
}

function onTrendConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.value.dashboard_trend_period = selectedValues[0]
  showTrendPicker.value = false
  onSave()
}

onMounted(async () => {
  try {
    const res = await getUserConfig()
    Object.assign(form.value, res.data)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.user-config-page {
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
.desc {
  display: block;
  margin-top: 4px;
  color: var(--van-text-color-2, #969799);
  font-size: 12px;
}
.skeleton {
  padding: 16px;
}
</style>
