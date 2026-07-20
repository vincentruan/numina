<script setup lang="ts">
import { ref, watch } from 'vue'
import { showSuccessToast, showFailToast } from 'vant'
import { recordSaving } from '@/api/wishes'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ show: boolean; wishId: string }>()
const emit = defineEmits<{ (e: 'update:show', v: boolean): void; (e: 'saved'): void }>()
const { t } = useI18n()

const amount = ref('')
const logDate = ref(new Date().toISOString().slice(0, 10))
const note = ref('')
const submitting = ref(false)
const showDatePicker = ref(false)
const datePickerValue = ref<string[]>(new Date().toISOString().slice(0, 10).split('-'))

watch(
  () => props.show,
  (v) => {
    if (v) {
      amount.value = ''
      logDate.value = new Date().toISOString().slice(0, 10)
      note.value = ''
      datePickerValue.value = logDate.value.split('-')
    }
  },
)

function onDateConfirm({ selectedValues }: { selectedValues: string[] }) {
  logDate.value = selectedValues.join('-')
  showDatePicker.value = false
}

async function onSubmit() {
  const amt = amount.value.trim()
  if (!amt || Number(amt) <= 0) {
    showFailToast(t('wish.savings.amountRequired'))
    return
  }
  submitting.value = true
  try {
    await recordSaving(props.wishId, amt, logDate.value, note.value.trim() || undefined)
    showSuccessToast(t('wish.savings.recorded'))
    emit('saved')
    emit('update:show', false)
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    submitting.value = false
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
    :style="{ maxHeight: '80%' }"
    @update:show="emit('update:show', $event)"
  >
    <div class="record-dialog">
      <div class="dialog-title">{{ t('wish.savings.recordTitle') }}</div>
      <van-form @submit="onSubmit">
        <van-cell-group inset>
          <van-field
            v-model="amount"
            name="amount"
            :label="t('wish.savings.amountLabel')"
            type="number"
            inputmode="decimal"
            :placeholder="t('wish.savings.amountPlaceholder')"
            :rules="[{ required: true, message: t('wish.savings.amountRequired') }]"
          />
          <van-field
            :model-value="logDate"
            readonly
            name="log_date"
            :label="t('wish.savings.dateLabel')"
            :placeholder="t('wish.savings.datePlaceholder')"
            @click="showDatePicker = true"
          />
          <van-field
            v-model="note"
            name="note"
            :label="t('wish.savings.noteLabel')"
            type="textarea"
            rows="2"
            autosize
            :placeholder="t('wish.savings.notePlaceholder')"
          />
        </van-cell-group>
        <div class="dialog-actions">
          <van-button block plain @click="close">{{ t('common.cancel') }}</van-button>
          <van-button block type="primary" native-type="submit" :loading="submitting">
            {{ t('wish.savings.recordBtn') }}
          </van-button>
        </div>
      </van-form>
    </div>
    <van-popup v-model:show="showDatePicker" position="bottom">
      <van-date-picker
        v-model="datePickerValue"
        :min-date="new Date(2020, 0, 1)"
        :max-date="new Date(2100, 11, 31)"
        @confirm="onDateConfirm"
        @cancel="showDatePicker = false"
      />
    </van-popup>
  </van-popup>
</template>

<style scoped>
.record-dialog {
  padding: 16px;
}
.dialog-title {
  font-size: 16px;
  font-weight: 600;
  text-align: center;
  margin-bottom: 12px;
}
.dialog-actions {
  display: flex;
  gap: 8px;
  margin: 12px 16px;
}
</style>
