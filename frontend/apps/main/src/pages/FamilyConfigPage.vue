<template>
  <div class="family-config-page">
    <van-nav-bar
      :title="t('familyConfig.title')"
      left-arrow
      @click-left="$router.back()"
    />

    <van-skeleton v-if="loading" :row="8" class="skeleton" />

    <template v-else>
      <!-- AI Cache Duration -->
      <van-cell-group inset :title="t('familyConfig.aiCacheGroup')" class="section">
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.aiCacheTtlReport') }}</span>
            <span class="value">{{ form.ai_cache_ttl_report }} {{ t('familyConfig.unitMinutes') }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.aiCacheTtlReportDesc') }}</span>
            <van-slider v-model="form.ai_cache_ttl_report" :min="5" :max="480" :step="5" @change="onSave" />
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.aiCacheTtlFinanceCoach') }}</span>
            <span class="value">{{ form.ai_cache_ttl_finance_coach }} {{ t('familyConfig.unitMinutes') }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.aiCacheTtlFinanceCoachDesc') }}</span>
            <van-slider v-model="form.ai_cache_ttl_finance_coach" :min="60" :max="1440" :step="30" @change="onSave" />
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.aiCacheTtlNarrative') }}</span>
            <span class="value">{{ form.ai_cache_ttl_dashboard_narrative }} {{ t('familyConfig.unitMinutes') }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.aiCacheTtlNarrativeDesc') }}</span>
            <van-slider v-model="form.ai_cache_ttl_dashboard_narrative" :min="30" :max="720" :step="30" @change="onSave" />
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Dashboard Thresholds -->
      <van-cell-group inset :title="t('familyConfig.dashboardGroup')" class="section">
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.minAssetCount') }}</span>
            <span class="value">{{ form.dashboard_min_asset_count }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.minAssetCountDesc') }}</span>
            <van-slider v-model="form.dashboard_min_asset_count" :min="1" :max="50" :step="1" @change="onSave" />
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.minHistoryMonths') }}</span>
            <span class="value">{{ form.dashboard_min_history_months }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.minHistoryMonthsDesc') }}</span>
            <van-slider v-model="form.dashboard_min_history_months" :min="1" :max="12" :step="1" @change="onSave" />
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.expiringDaysThreshold') }}</span>
            <span class="value">{{ form.dashboard_expiring_days_threshold }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.expiringDaysThresholdDesc') }}</span>
            <van-slider v-model="form.dashboard_expiring_days_threshold" :min="7" :max="365" :step="7" @change="onSave" />
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Scheduled Tasks (disabled note) -->
      <van-cell-group inset :title="t('familyConfig.scheduledGroup')" class="section">
        <van-cell :label="t('familyConfig.scheduledDisabled')" />
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.monthlyReportDay') }}</span>
            <span class="value">{{ form.scheduled_monthly_report_day }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.monthlyReportDayDesc') }}</span>
            <van-slider v-model="form.scheduled_monthly_report_day" :min="1" :max="28" :step="1" @change="onSave" />
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.monthlyReportHour') }}</span>
            <span class="value">{{ form.scheduled_monthly_report_hour }} {{ t('familyConfig.unitHour') }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.monthlyReportHourDesc') }}</span>
            <van-slider v-model="form.scheduled_monthly_report_hour" :min="0" :max="23" :step="1" @change="onSave" />
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.weeklyScanDay') }}</span>
            <span class="value">{{ dayLabels[form.scheduled_weekly_scan_day] }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.weeklyScanDayDesc') }}</span>
            <van-slider v-model="form.scheduled_weekly_scan_day" :min="0" :max="6" :step="1" @change="onSave" />
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.weeklyScanHour') }}</span>
            <span class="value">{{ form.scheduled_weekly_scan_hour }} {{ t('familyConfig.unitHour') }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.weeklyScanHourDesc') }}</span>
            <van-slider v-model="form.scheduled_weekly_scan_hour" :min="0" :max="23" :step="1" @change="onSave" />
          </template>
        </van-cell>
      </van-cell-group>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { getFamilyConfig, updateFamilyConfig } from '@/api/config'

defineOptions({ name: 'FamilyConfig' })

const { t } = useI18n()
const loading = ref(true)

const dayLabels = computed<string[]>(() => {
  const labels = t('familyConfig.dayLabels', { returnObjects: true })
  return Array.isArray(labels) ? labels : []
})

const form = ref({
  ai_cache_ttl_report: 60,
  ai_cache_ttl_finance_coach: 480,
  ai_cache_ttl_dashboard_narrative: 240,
  dashboard_min_asset_count: 5,
  dashboard_min_history_months: 1,
  dashboard_expiring_days_threshold: 180,
  scheduled_monthly_report_day: 1,
  scheduled_monthly_report_hour: 8,
  scheduled_weekly_scan_day: 0,
  scheduled_weekly_scan_hour: 8,
})

let saveTimer: ReturnType<typeof setTimeout> | null = null

function onSave() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    try {
      await updateFamilyConfig(form.value)
      showSuccessToast(t('toast.familyConfigSaved'))
    } catch {
      showFailToast(t('toast.operationFailed2'))
    }
  }, 600)
}

onMounted(async () => {
  try {
    const res = await getFamilyConfig()
    Object.assign(form.value, res.data)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.family-config-page {
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
