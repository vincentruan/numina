<template>
  <div class="challenge-creator">
    <p class="creator-title">{{ t('challenge.create') }}</p>

    <van-cell-group inset>
      <!-- Child selector -->
      <van-field
        v-model="selectedChildName"
        is-link
        readonly
        :label="t('challenge.selectChild')"
        :placeholder="t('challenge.selectChild')"
        @click="showChildPicker = true"
      />

      <!-- Target type selector -->
      <van-field
        v-model="selectedTypeName"
        is-link
        readonly
        :label="t('challenge.targetType')"
        :placeholder="t('challenge.targetType')"
        @click="showTypePicker = true"
      />

      <!-- Target value input -->
      <van-field
        v-model="targetValueStr"
        type="digit"
        :label="t('challenge.targetValue')"
        :placeholder="t('challenge.targetValue')"
      />

      <!-- Deadline picker -->
      <van-field
        v-model="deadlineLabel"
        is-link
        readonly
        :label="t('challenge.deadline')"
        :placeholder="t('challenge.deadline')"
        @click="showDeadlinePicker = true"
      />

      <!-- Chore template picker (only for specific_chore) -->
      <van-field
        v-if="form.target_type === 'specific_chore'"
        v-model="selectedTemplateName"
        is-link
        readonly
        :label="t('challenge.selectChore')"
        :placeholder="t('challenge.selectChore')"
        @click="showTemplatePicker = true"
      />

      <!-- Message input -->
      <van-field
        v-model="form.message"
        :label="t('challenge.encouragement')"
        :placeholder="t('challenge.encouragement')"
        maxlength="100"
        show-word-limit
      />
    </van-cell-group>

    <van-button
      block
      type="primary"
      :disabled="!isValid"
      class="create-btn"
      @click="doCreate"
    >
      {{ t('challenge.create') }}
    </van-button>

    <!-- Child picker popup -->
    <van-popup v-model:show="showChildPicker" position="bottom" round>
      <van-picker
        :columns="childColumns"
        @confirm="onChildConfirm"
        @cancel="showChildPicker = false"
      />
    </van-popup>

    <!-- Type picker popup -->
    <van-popup v-model:show="showTypePicker" position="bottom" round>
      <van-picker
        :columns="typeColumns"
        @confirm="onTypeConfirm"
        @cancel="showTypePicker = false"
      />
    </van-popup>

    <!-- Deadline picker popup -->
    <van-popup v-model:show="showDeadlinePicker" position="bottom" round>
      <van-date-picker
        v-model="deadlineDate"
        :min-date="minDeadline"
        @confirm="onDeadlineConfirm"
        @cancel="showDeadlinePicker = false"
      />
    </van-popup>

    <!-- Template picker popup -->
    <van-popup v-model:show="showTemplatePicker" position="bottom" round>
      <van-picker
        :columns="templateColumns"
        @confirm="onTemplateConfirm"
        @cancel="showTemplatePicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast, showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { listChildren, type ChildResponse } from '@/api/children'
import { listChoreTemplates, type ChoreTemplate } from '@/api/chores'
import { createChallenge, type ChallengeCreateRequest } from '@/api/challengeGrant'

const { t } = useI18n()

const form = ref<ChallengeCreateRequest>({
  child_user_id: '',
  target_type: 'task_count',
  target_value: 0,
  deadline: '',
  message: '',
  chore_template_id: undefined,
})

const children = ref<ChildResponse[]>([])
const templates = ref<ChoreTemplate[]>([])
const showChildPicker = ref(false)
const showTypePicker = ref(false)
const showDeadlinePicker = ref(false)
const showTemplatePicker = ref(false)
const deadlineDate = ref<string[]>([])

const minDeadline = computed(() => {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d
})

const selectedChildName = ref('')
const selectedTypeName = ref('')
const selectedTemplateName = ref('')
const targetValueStr = ref('')
const deadlineLabel = ref('')

const childColumns = computed(() =>
  children.value.map(c => ({ text: c.display_name, value: c.id }))
)

const typeColumns = computed(() => [
  { text: t('challenge.taskCount'), value: 'task_count' },
  { text: t('challenge.streakLength'), value: 'streak_length' },
  { text: t('challenge.specificChore'), value: 'specific_chore' },
  { text: t('challenge.starEarnings'), value: 'star_earnings' },
])

const templateColumns = computed(() =>
  templates.value.map(t => ({ text: `${t.emoji || '📋'} ${t.name}`, value: t.id }))
)

const isValid = computed(() => {
  if (!form.value.child_user_id) return false
  if (!form.value.target_value || form.value.target_value <= 0) return false
  if (!form.value.deadline) return false
  if (form.value.target_type === 'specific_chore' && !form.value.chore_template_id) return false
  return true
})

function onChildConfirm({ selectedOptions }: { selectedOptions: Array<{ text: string; value: string }> }) {
  const opt = selectedOptions[0]
  form.value.child_user_id = opt.value
  selectedChildName.value = opt.text
  showChildPicker.value = false
}

function onTypeConfirm({ selectedOptions }: { selectedOptions: Array<{ text: string; value: string }> }) {
  const opt = selectedOptions[0]
  form.value.target_type = opt.value as ChallengeCreateRequest['target_type']
  selectedTypeName.value = opt.text
  if (form.value.target_type !== 'specific_chore') {
    form.value.chore_template_id = undefined
    selectedTemplateName.value = ''
  }
  showTypePicker.value = false
}

function onDeadlineConfirm({ selectedValues }: { selectedValues: string[] }) {
  const [year, month, day] = selectedValues
  form.value.deadline = `${year}-${month}-${day}T23:59:59`
  deadlineLabel.value = `${year}-${month}-${day}`
  showDeadlinePicker.value = false
}

function onTemplateConfirm({ selectedOptions }: { selectedOptions: Array<{ text: string; value: string }> }) {
  const opt = selectedOptions[0]
  form.value.chore_template_id = opt.value
  selectedTemplateName.value = opt.text
  showTemplatePicker.value = false
}

async function doCreate() {
  form.value.target_value = parseInt(targetValueStr.value) || 0
  if (!isValid.value) return

  try {
    await createChallenge(form.value)
    showSuccessToast(t('challenge.createdSuccess'))
    // Reset form
    form.value = {
      child_user_id: '',
      target_type: 'task_count',
      target_value: 0,
      deadline: '',
      message: '',
      chore_template_id: undefined,
    }
    selectedChildName.value = ''
    selectedTypeName.value = ''
    selectedTemplateName.value = ''
    targetValueStr.value = ''
    deadlineLabel.value = ''
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { message?: string } }; message?: string })?.response?.data?.message || (e as Error).message || t('common.failed')
    showToast(msg)
  }
}

onMounted(async () => {
  try {
    children.value = await listChildren()
    templates.value = await listChoreTemplates()
  } catch {
    // non-blocking
  }
})
</script>

<style scoped>
.challenge-creator {
  padding: var(--space-md);
}

.creator-title {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 12px;
}

.create-btn {
  margin-top: 16px;
}
</style>