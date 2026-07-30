<script setup lang="ts">
import { ref, watch } from 'vue'
import { showSuccessToast, showFailToast } from 'vant'
import { getSavingsLog, deleteSavingsLog } from '@/api/wishes'
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import BottomSheetConfirm from '@/components/BottomSheetConfirm.vue'
import type { SavingsLog } from '@/types'

const props = defineProps<{ show: boolean; wishId: string }>()
const emit = defineEmits<{ (e: 'update:show', v: boolean): void; (e: 'changed'): void }>()
const { t } = useI18n()
const { format } = useCurrency()
const logs = ref<SavingsLog[]>([])
const loading = ref(false)
const deleteSheet = ref({ show: false, description: '', log: null as SavingsLog | null })

watch(
  () => props.show,
  async (v) => {
    if (v && props.wishId) {
      loading.value = true
      try {
        const r = await getSavingsLog(props.wishId)
        logs.value = r.data
      } catch {
        logs.value = []
      } finally {
        loading.value = false
      }
    }
  },
)

function onDelete(log: SavingsLog) {
  deleteSheet.value.description = t('wish.savings.deleteConfirm', { amount: format(Number(log.amount)) })
  deleteSheet.value.log = log
  deleteSheet.value.show = true
}

async function executeDeleteSavingsLog() {
  const log = deleteSheet.value.log
  if (!log) return
  try {
    await deleteSavingsLog(props.wishId, log.id)
    logs.value = logs.value.filter((l) => l.id !== log.id)
    showSuccessToast(t('wish.savings.deleted'))
    emit('changed') // parent refreshes progress + saved_amount
    deleteSheet.value.show = false
  } catch {
    showFailToast(t('toast.operationFailed'))
  }
}

function close() {
  emit('update:show', false)
}
</script>

<template>
  <van-popup
    :show="show"
    position="bottom"
    round
    :style="{ maxHeight: '70%' }"
    @update:show="emit('update:show', $event)"
  >
    <div class="log-dialog">
      <div class="dialog-title">{{ t('wish.savings.logTitle') }}</div>
      <van-empty v-if="!loading && logs.length === 0" :description="t('wish.savings.logEmpty')" />
      <van-loading v-else-if="loading" />
      <ul v-else class="log-list">
        <li v-for="log in logs" :key="log.id" class="log-item">
          <div class="log-main">
            <span class="log-amount">{{ format(Number(log.amount)) }}</span>
            <span class="log-date">{{ log.log_date }}</span>
          </div>
          <div v-if="log.note" class="log-note">{{ log.note }}</div>
          <van-button size="mini" plain type="danger" @click="onDelete(log)">{{ t('common.delete') }}</van-button>
        </li>
      </ul>
      <div class="dialog-actions">
        <van-button block plain @click="close">{{ t('common.close') }}</van-button>
      </div>
    </div>
    <!-- Destructive confirm: delete savings log -->
    <BottomSheetConfirm
      v-model:show="deleteSheet.show"
      :title="t('wish.savings.deleteTitle')"
      :description="deleteSheet.description"
      :impact-preview="t('bottomSheet.impactSavingsLogDelete')"
      @confirm="executeDeleteSavingsLog"
    />
  </van-popup>
</template>

<style scoped>
.log-dialog {
  padding: 16px;
}
.dialog-title {
  font-size: 16px;
  font-weight: 600;
  text-align: center;
  margin-bottom: 12px;
}
.log-list {
  list-style: none;
  padding: 0;
  margin: 0 0 12px;
}
.log-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 0;
  border-bottom: 1px solid var(--separator, #eee);
}
.log-main {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}
.log-amount {
  font-weight: 600;
  color: var(--color-primary, #6366f1);
}
.log-date {
  color: var(--text-secondary, #969799);
  font-size: 12px;
}
.log-note {
  font-size: 12px;
  color: var(--text-secondary, #969799);
}
.dialog-actions {
  margin-top: 12px;
}
</style>
