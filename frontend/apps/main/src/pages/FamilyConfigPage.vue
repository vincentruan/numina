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
            <span class="value">{{ hourRefs.report }} {{ t('familyConfig.unitHours') }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.aiCacheTtlReportDesc') }}</span>
            <div class="slider-track">
              <van-slider v-model="hourRefs.report" :min="1" :max="168" :step="12" @change="onSave" />
            </div>
            <div class="slider-scale"><span>1</span><span>84</span><span>168</span></div>
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.aiCacheTtlFinanceCoach') }}</span>
            <span class="value">{{ hourRefs.financeCoach }} {{ t('familyConfig.unitHours') }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.aiCacheTtlFinanceCoachDesc') }}</span>
            <div class="slider-track">
              <van-slider v-model="hourRefs.financeCoach" :min="1" :max="168" :step="12" @change="onSave" />
            </div>
            <div class="slider-scale"><span>1</span><span>84</span><span>168</span></div>
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.aiCacheTtlNarrative') }}</span>
            <span class="value">{{ hourRefs.narrative }} {{ t('familyConfig.unitHours') }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.aiCacheTtlNarrativeDesc') }}</span>
            <div class="slider-track">
              <van-slider v-model="hourRefs.narrative" :min="1" :max="168" :step="12" @change="onSave" />
            </div>
            <div class="slider-scale"><span>1</span><span>84</span><span>168</span></div>
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
            <div class="slider-track">
              <van-slider v-model="form.dashboard_min_asset_count" :min="1" :max="50" :step="1" @change="onSave" />
            </div>
            <div class="slider-scale"><span>1</span><span>25</span><span>50</span></div>
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.minHistoryMonths') }}</span>
            <span class="value">{{ form.dashboard_min_history_months }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.minHistoryMonthsDesc') }}</span>
            <div class="slider-track">
              <van-slider v-model="form.dashboard_min_history_months" :min="1" :max="12" :step="1" @change="onSave" />
            </div>
            <div class="slider-scale"><span>1</span><span>6</span><span>12</span></div>
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.expiringDaysThreshold') }}</span>
            <span class="value">{{ form.dashboard_expiring_days_threshold }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.expiringDaysThresholdDesc') }}</span>
            <div class="slider-track">
              <van-slider v-model="form.dashboard_expiring_days_threshold" :min="7" :max="365" :step="7" @change="onSave" />
            </div>
            <div class="slider-scale"><span>7</span><span>182</span><span>365</span></div>
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
            <div class="slider-track">
              <van-slider v-model="form.scheduled_monthly_report_day" :min="1" :max="28" :step="1" @change="onSave" />
            </div>
            <div class="slider-scale"><span>1</span><span>14</span><span>28</span></div>
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.monthlyReportHour') }}</span>
            <span class="value">{{ form.scheduled_monthly_report_hour }} {{ t('familyConfig.unitHour') }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.monthlyReportHourDesc') }}</span>
            <div class="slider-track">
              <van-slider v-model="form.scheduled_monthly_report_hour" :min="0" :max="23" :step="1" @change="onSave" />
            </div>
            <div class="slider-scale"><span>0</span><span>12</span><span>23</span></div>
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.weeklyScanDay') }}</span>
            <span class="value">{{ dayLabels[form.scheduled_weekly_scan_day] }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.weeklyScanDayDesc') }}</span>
            <div class="slider-track">
              <van-slider v-model="form.scheduled_weekly_scan_day" :min="0" :max="6" :step="1" @change="onSave" />
            </div>
            <div class="slider-scale"><span>0</span><span>3</span><span>6</span></div>
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.weeklyScanHour') }}</span>
            <span class="value">{{ form.scheduled_weekly_scan_hour }} {{ t('familyConfig.unitHour') }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.weeklyScanHourDesc') }}</span>
            <div class="slider-track">
              <van-slider v-model="form.scheduled_weekly_scan_hour" :min="0" :max="23" :step="1" @change="onSave" />
            </div>
            <div class="slider-scale"><span>0</span><span>12</span><span>23</span></div>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Financial Literacy -->
      <van-cell-group inset :title="t('familyConfig.literacyGroup')" class="section">
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.literacyReportDay') }}</span>
            <span class="value">{{ dayLabels[form.literacy_report_day] }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.literacyReportDayDesc') }}</span>
            <div class="slider-track">
              <van-slider v-model="form.literacy_report_day" :min="0" :max="6" :step="1" @change="onSave" />
            </div>
            <div class="slider-scale"><span>0</span><span>3</span><span>6</span></div>
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.literacyReportHour') }}</span>
            <span class="value">{{ form.literacy_report_hour }} {{ t('familyConfig.unitHour') }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.literacyReportHourDesc') }}</span>
            <div class="slider-track">
              <van-slider v-model="form.literacy_report_hour" :min="0" :max="23" :step="1" @change="onSave" />
            </div>
            <div class="slider-scale"><span>0</span><span>12</span><span>23</span></div>
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.literacyCacheTtl') }}</span>
            <span class="value">{{ hourRefs.literacyWeeklyReport }} {{ t('familyConfig.unitHours') }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('familyConfig.literacyCacheTtlDesc') }}</span>
            <div class="slider-track">
              <van-slider v-model="hourRefs.literacyWeeklyReport" :min="1" :max="168" :step="12" @change="onSave" />
            </div>
            <div class="slider-scale"><span>1</span><span>84</span><span>168</span></div>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Star Coin Exchange Rates (owner-only) -->
      <van-cell-group v-if="isOwner" inset :title="t('familyConfig.coinRateGroup')" class="section">
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.copperToSilverRate') }}</span>
            <span class="value">{{ coinCopperToSilver }}</span>
          </template>
          <template #label>
            <div class="slider-track">
              <van-slider v-model="coinCopperToSilver" :min="1" :max="10" :step="1" @change="onCopperToSilverChange" />
            </div>
            <div class="slider-scale"><span>1</span><span>5</span><span>10</span></div>
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('familyConfig.silverToGoldRate') }}</span>
            <span class="value">{{ coinSilverToGold }}</span>
          </template>
          <template #label>
            <div class="slider-track">
              <van-slider v-model="coinSilverToGold" :min="1" :max="10" :step="1" @change="onSilverToGoldChange" />
            </div>
            <div class="slider-scale"><span>1</span><span>5</span><span>10</span></div>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Education & Auto-Approve (owner-only) -->
      <van-cell-group v-if="isOwner" inset :title="t('settings.educationRewardSection')" class="section">
        <van-cell center :title="t('settings.educationRewardEnabled')">
          <template #right-icon>
            <van-switch v-model="educationRewardEnabled" size="20" @update:model-value="onEducationRewardToggle" />
          </template>
        </van-cell>
        <van-cell :title="t('settings.educationRewardRate')">
          <template #label>
            <span class="desc">{{ t('settings.educationRewardRateUnit', { rate: coinToYuanRate }) }}</span>
            <div class="slider-track">
              <van-slider v-model="coinToYuanRate" :min="1" :max="10" :step="1" @change="onCoinToYuanChange" />
            </div>
            <div class="slider-scale"><span>1</span><span>5</span><span>10</span></div>
          </template>
        </van-cell>
        <van-cell>
          <template #title>
            <span>{{ t('settings.autoApproveHours') }}</span>
            <span class="value">{{ autoApproveHours === 0 ? t('settings.autoApproveHoursManual') : `${autoApproveHours} ${t('settings.autoApproveHoursUnit')}` }}</span>
          </template>
          <template #label>
            <span class="desc">{{ t('settings.autoApproveHoursDesc') }}</span>
            <div class="slider-track">
              <van-slider v-model="autoApproveHours" :min="0" :max="72" :step="1" @change="onAutoApproveChange" />
            </div>
            <div class="slider-scale"><span>0</span><span>36</span><span>72</span></div>
          </template>
        </van-cell>
      </van-cell-group>

    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onActivated, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { getFamilyConfig, updateFamilyConfig } from '@/api/config'
import { getFamilySettings, updateFamilySettings } from '@/api/family'
import { useAuth } from '@/composables/useAuth'
import { useFamilyStore } from '@/stores/family'

defineOptions({ name: 'FamilyConfig' })

const { t } = useI18n()
const { isOwner } = useAuth()
const familyStore = useFamilyStore()
const loading = ref(true)
// Block auto-save until initial data is loaded (prevents saving default values
// before loadFamilyConfig completes and overwrites them with API data)
const initializing = ref(true)
const educationRewardEnabled = ref(false)
const coinToYuanRate = ref(1)
const autoApproveHours = ref(0)
const coinCopperToSilver = ref(10)
const coinSilverToGold = ref(10)

const dayLabels = computed<string[]>(() => {
  const labels = t('familyConfig.dayLabels', { returnObjects: true }) as unknown
  return Array.isArray(labels) ? labels as string[] : []
})

const form = ref({
  ai_cache_ttl_report: 60,
  ai_cache_ttl_finance_coach: 480,
  ai_cache_ttl_dashboard_narrative: 1440,
  dashboard_min_asset_count: 5,
  dashboard_min_history_months: 1,
  dashboard_expiring_days_threshold: 180,
  scheduled_monthly_report_day: 1,
  scheduled_monthly_report_hour: 8,
  scheduled_weekly_scan_day: 0,
  scheduled_weekly_scan_hour: 8,
  literacy_report_day: 0,
  literacy_report_hour: 8,
  ai_cache_ttl_literacy_weekly_report: 10080,
})

// AI cache TTL: form stores MINUTES (backend storage + cache logic unit), hourRefs stores HOURS (UI display unit)
// Backend config_registry defines min/max/step in minutes; cache consumers (ai_report.py, finance_coach_cache.py) use timedelta(minutes=ttl)
const hourRefs = reactive({
  report: 1,
  financeCoach: 8,
  narrative: 24,
  literacyWeeklyReport: 168,
})

let saveTimer: ReturnType<typeof setTimeout> | null = null

onUnmounted(() => {
  if (saveTimer) clearTimeout(saveTimer)
})

function onSave() {
  console.log('[FamilyConfig] onSave called, initializing:', initializing.value, 'hourRefs:', JSON.stringify({
    report: hourRefs.report,
    coach: hourRefs.financeCoach,
    narrative: hourRefs.narrative,
    literacy: hourRefs.literacyWeeklyReport,
  }))
  // Block auto-save during initial data load to prevent sending default values
  if (initializing.value) {
    console.log('[FamilyConfig] onSave blocked by initializing')
    return
  }
  // Convert UI hours → backend minutes before persisting.
  // All ai_cache_ttl_* fields are stored and consumed as MINUTES in the backend
  // (config_registry definitions, timedelta(minutes=ttl) in cache consumers).
  form.value.ai_cache_ttl_report = hourRefs.report * 60
  form.value.ai_cache_ttl_finance_coach = hourRefs.financeCoach * 60
  form.value.ai_cache_ttl_dashboard_narrative = hourRefs.narrative * 60
  form.value.ai_cache_ttl_literacy_weekly_report = hourRefs.literacyWeeklyReport * 60
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

function onCopperToSilverChange() {
  updateFamilySettings({ coinCopperToSilver: coinCopperToSilver.value })
    .then(() => {
      familyStore.coinCopperToSilver = coinCopperToSilver.value
      showSuccessToast(t('toast.saveSuccess'))
    })
    .catch(() => {
      showFailToast(t('toast.saveFailed'))
    })
}

function onSilverToGoldChange() {
  updateFamilySettings({ coinSilverToGold: coinSilverToGold.value })
    .then(() => {
      familyStore.coinSilverToGold = coinSilverToGold.value
      showSuccessToast(t('toast.saveSuccess'))
    })
    .catch(() => {
      showFailToast(t('toast.saveFailed'))
    })
}

function onEducationRewardToggle() {
  updateFamilySettings({ educationRewardEnabled: educationRewardEnabled.value })
    .then(() => {
      familyStore.educationRewardEnabled = educationRewardEnabled.value
      showSuccessToast(t('toast.saveSuccess'))
    })
    .catch(() => {
      showFailToast(t('toast.saveFailed'))
    })
}

function onCoinToYuanChange() {
  updateFamilySettings({ coinToYuanRate: coinToYuanRate.value })
    .then(() => {
      familyStore.coinToYuanRate = coinToYuanRate.value
      showSuccessToast(t('toast.saveSuccess'))
    })
    .catch(() => {
      showFailToast(t('toast.saveFailed'))
    })
}

function onAutoApproveChange() {
  updateFamilySettings({ autoApproveHours: autoApproveHours.value })
    .then(() => {
      showSuccessToast(t('toast.saveSuccess'))
    })
    .catch(() => {
      showFailToast(t('toast.saveFailed'))
    })
}

async function loadFamilyConfig() {
  loading.value = true
  console.log('[FamilyConfig] loadFamilyConfig START, initializing:', initializing.value)
  try {
    const res = await getFamilyConfig()
    console.log('[FamilyConfig] API response:', JSON.stringify(res.data))
    // Reset form with API data to clear any corrupted values
    form.value = {
      ...form.value,
      ...res.data,
    }
    console.log('[FamilyConfig] form after assign:', JSON.stringify({
      coach: form.value.ai_cache_ttl_finance_coach,
      literacy: form.value.ai_cache_ttl_literacy_weekly_report,
    }))
    // Sync backend minutes → UI hours for display
    const toHours = (v: number) => Math.max(1, Math.min(168, Math.round(v / 60)))
    hourRefs.report = toHours(form.value.ai_cache_ttl_report)
    hourRefs.financeCoach = toHours(form.value.ai_cache_ttl_finance_coach)
    hourRefs.narrative = toHours(form.value.ai_cache_ttl_dashboard_narrative)
    hourRefs.literacyWeeklyReport = toHours(form.value.ai_cache_ttl_literacy_weekly_report)
    console.log('[FamilyConfig] hourRefs after toHours:', JSON.stringify({
      coach: hourRefs.financeCoach,
      literacy: hourRefs.literacyWeeklyReport,
    }))
  } catch (error) {
    console.error('[FamilyConfig] Failed to load family config:', error)
    showFailToast(t('toast.operationFailed2'))
  } finally {
    loading.value = false
    // Defer initializing=false to nextTick so that @update:model-value events
    // triggered by hourRefs changes are still blocked by the initializing guard
    nextTick(() => {
      initializing.value = false
      console.log('[FamilyConfig] initializing set to false')
    })
  }
}

onMounted(() => {
  loadFamilyConfig()
  loadEducationSettings()
})

onActivated(() => {
  loadFamilyConfig()
})

async function loadEducationSettings() {
  try {
    const res = await getFamilySettings()
    educationRewardEnabled.value = res.data.education_reward_enabled
    coinToYuanRate.value = res.data.coin_to_yuan_rate
    autoApproveHours.value = res.data.auto_approve_hours
    coinCopperToSilver.value = res.data.coin_copper_to_silver
    coinSilverToGold.value = res.data.coin_silver_to_gold
  } catch {
    // non-critical
  }
}
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
.skeleton {
  padding: 16px;
}
</style>
