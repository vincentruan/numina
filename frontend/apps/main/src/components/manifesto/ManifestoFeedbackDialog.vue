<template>
  <van-popup
    :show="visible"
    position="bottom"
    round
    :style="{ maxHeight: '70vh' }"
    @update:show="(val: boolean) => emit('update:visible', val)"
  >
    <div class="feedback-dialog">
      <h3 class="feedback-title">{{ t('manifesto.feedbackTitle') }}</h3>
      <van-field
        v-model="content"
        type="textarea"
        :maxlength="500"
        autosize
        :placeholder="t('manifesto.feedbackPlaceholder')"
        show-word-limit
      />
      <van-button
        type="primary"
        block
        :loading="submitting"
        :disabled="!content.trim()"
        @click="onSubmit"
      >
        {{ t('common.submit') }}
      </van-button>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showSuccessToast } from 'vant'
import * as manifestoApi from '@/api/manifesto'

const { t } = useI18n()

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submitted: []
}>()

const content = ref('')
const submitting = ref(false)

async function onSubmit() {
  if (!content.value.trim()) return
  submitting.value = true
  try {
    await manifestoApi.submitFeedback(content.value.trim())
    showSuccessToast(t('manifesto.feedbackSuccess'))
    content.value = ''
    emit('submitted')
    emit('update:visible', false)
  } catch {
    // error toast handled by axios interceptor
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.feedback-dialog {
  padding: 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.feedback-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
  margin: 0;
  text-align: center;
}
</style>
