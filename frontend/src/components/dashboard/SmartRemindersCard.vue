<template>
  <van-cell-group inset class="chart-section">
    <van-collapse v-model="expanded" @change="onToggle">
      <van-collapse-item name="reminders">
        <template #title>
          <span>🔔 {{ t('reminders.title') }}</span>
          <span v-if="store.summary.total > 0" class="reminder-summary">
            <template v-if="store.summary.expiring_soon > 0">到期 {{ store.summary.expiring_soon }}</template>
            <template v-if="store.summary.maturity > 0"> · 理财 {{ store.summary.maturity }}</template>
            <template v-if="store.summary.allocation_drift > 0"> · 失衡 {{ store.summary.allocation_drift }}</template>
            <template v-if="store.summary.large_purchase > 0"> · 冷静期 {{ store.summary.large_purchase }}</template>
          </span>
          <span v-else class="reminder-summary reminder-summary--empty">暂无提醒</span>
        </template>

        <van-loading v-if="store.loading" size="24px" class="reminder-loading" />
        <van-empty
          v-else-if="store.reminders.length === 0"
          :description="t('reminders.empty')"
          image-size="60"
        />
        <template v-else>
          <van-swipe-cell v-for="reminder in store.reminders" :key="reminder.id">
            <van-cell
              :title="reminder.title"
              :label="reminder.body"
              :icon="severityIcon(reminder.severity)"
            />
            <template #right>
              <van-button
                square
                type="warning"
                :text="t('reminders.dismiss')"
                class="dismiss-btn"
                @click="onDismiss(reminder.id)"
              />
            </template>
          </van-swipe-cell>
        </template>
      </van-collapse-item>
    </van-collapse>
  </van-cell-group>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRemindersStore } from '@/stores/reminders'

const { t } = useI18n()
const store = useRemindersStore()
const expanded = ref<string[]>([])
const loaded = ref(false)

onMounted(() => {
  store.fetchSummary()
})

async function onToggle(names: string[]) {
  if (names.includes('reminders') && !loaded.value) {
    loaded.value = true
    await store.fetchReminders()
  }
}

async function onDismiss(id: number) {
  await store.dismiss(id)
}

function severityIcon(severity: string): string {
  if (severity === 'critical') return 'warning-o'
  if (severity === 'warning') return 'info-o'
  return 'bell'
}
</script>

<style scoped>
.reminder-summary {
  margin-left: 8px;
  font-size: 12px;
  color: var(--van-text-color-2);
}
.reminder-summary--empty {
  color: var(--van-text-color-3);
}
.reminder-loading {
  display: flex;
  justify-content: center;
  padding: 16px;
}
.dismiss-btn {
  height: 100%;
}
</style>
