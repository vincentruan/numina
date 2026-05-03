<template>
  <van-nav-bar
    :title="t('reminders.thresholdSettings')"
    left-arrow
    @click-left="$router.back()"
  />

  <div class="page-content">
    <van-cell-group inset :title="t('reminders.thresholdGroupTitle')" class="section">
      <van-field
        v-model="fixedThreshold"
        :label="t('reminders.thresholdFixed')"
        type="number"
        placeholder="如 5000"
        clearable
      />
      <van-field
        v-model="multiplierThreshold"
        :label="t('reminders.thresholdMultiplier')"
        type="number"
        placeholder="如 2"
        clearable
      />
      <van-cell>
        <van-button type="primary" size="small" block @click="saveConfig">{{ t('reminders.saveThreshold') }}</van-button>
      </van-cell>
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { notificationChannelsApi } from '@/api/notificationChannels'

const { t } = useI18n()

const fixedThreshold = ref('')
const multiplierThreshold = ref('')

onMounted(async () => {
  const config = await notificationChannelsApi.getConfig()
  fixedThreshold.value = config.large_purchase_threshold_fixed?.toString() ?? ''
  multiplierThreshold.value = config.large_purchase_threshold_multiplier?.toString() ?? ''
})

async function saveConfig() {
  await notificationChannelsApi.updateConfig({
    large_purchase_threshold_fixed: fixedThreshold.value ? parseFloat(fixedThreshold.value) : null,
    large_purchase_threshold_multiplier: multiplierThreshold.value
      ? parseFloat(multiplierThreshold.value)
      : null,
  })
  showToast(t('toast.configSaved'))
}
</script>

<style scoped>
.page-content {
  padding-bottom: 32px;
}
.section {
  margin-top: 12px;
}
</style>
