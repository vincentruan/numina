<template>
  <van-nav-bar
    :title="t('reminders.thresholdSettings')"
    left-arrow
    @click-left="$router.back()"
  />

  <div class="page-content">
    <!-- Large-purchase linkage status -->
    <van-cell-group v-if="largePurchase" inset :title="t('reminders.largePurchaseThresholdStatusTitle')" class="section">
      <van-cell>
        <template #title>
          <span>{{ t('reminders.thresholdConfiguredLabel') }}</span>
        </template>
        <template #value>
          <van-tag :type="largePurchase.threshold_configured ? 'success' : 'warning'">
            {{ largePurchase.threshold_configured ? '✓' : '!' }}
          </van-tag>
        </template>
      </van-cell>
      <van-cell>
        <template #title>
          <span>{{ t('reminders.subscriberCountLabel', { count: largePurchase.subscribing_channel_count }) }}</span>
        </template>
        <template #value>
          <span v-if="largePurchase.subscribing_channel_count > 0">
            {{ t('reminders.subscribingChannelsList', { names: largePurchase.subscribing_channel_names.join(', ') }) }}
          </span>
          <van-button
            v-else
            plain
            type="primary"
            size="mini"
            @click="$router.push('/settings/notifications')"
          >
            {{ t('reminders.goConfigureChannels') }}
          </van-button>
        </template>
      </van-cell>
    </van-cell-group>

    <van-cell-group inset :title="t('reminders.thresholdGroupTitle')" class="section">
      <van-field
        v-model="fixedThreshold"
        :label="t('reminders.thresholdFixed')"
        type="number"
        :placeholder="t('reminders.thresholdFixedPlaceholder')"
        clearable
      />
      <van-field
        v-model="multiplierThreshold"
        :label="t('reminders.thresholdMultiplier')"
        type="number"
        :placeholder="t('reminders.thresholdMultiplierPlaceholder')"
        clearable
      />
      <van-cell>
        <van-button type="primary" size="small" block @click="saveConfig">{{ t('reminders.saveThreshold') }}</van-button>
      </van-cell>
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { notificationChannelsApi, type NotificationFeatureStatus } from '@/api/notificationChannels'

const { t } = useI18n()

const fixedThreshold = ref('')
const multiplierThreshold = ref('')
const status = ref<NotificationFeatureStatus | null>(null)
const largePurchase = computed(() => status.value?.large_purchase)

onMounted(async () => {
  const [config, statusResult] = await Promise.all([
    notificationChannelsApi.getConfig(),
    notificationChannelsApi.getFeatureStatus().catch(() => null),
  ])
  fixedThreshold.value = config.large_purchase_threshold_fixed?.toString() ?? ''
  multiplierThreshold.value = config.large_purchase_threshold_multiplier?.toString() ?? ''
  status.value = statusResult
})

async function saveConfig() {
  await notificationChannelsApi.updateConfig({
    large_purchase_threshold_fixed: fixedThreshold.value ? parseFloat(fixedThreshold.value) : null,
    large_purchase_threshold_multiplier: multiplierThreshold.value
      ? parseFloat(multiplierThreshold.value)
      : null,
  })
  // Refresh status after saving threshold so the linkage card reflects the
  // new reality without the user having to navigate away.
  status.value = await notificationChannelsApi.getFeatureStatus().catch(() => status.value)
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
