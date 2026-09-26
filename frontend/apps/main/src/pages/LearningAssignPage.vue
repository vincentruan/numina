<template>
  <div class="learning-assign-page">
    <PageHeader :title="t('learning.assignTask')" />

    <van-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-width="80"
      class="assign-form"
    >
      <!-- Child selector -->
      <van-cell-group inset>
        <van-field
          v-model="selectedChildName"
          is-link
          readonly
          :label="t('learning.selectChild')"
          :placeholder="t('learning.selectChildPlaceholder')"
          @click="showChildPicker = true"
        />
      </van-cell-group>

      <!-- Topic search -->
      <van-cell-group inset class="topic-section">
        <van-field
          v-model="searchQuery"
          :label="t('learning.topicSearch')"
          :placeholder="t('learning.topicSearchPlaceholder')"
          clearable
          @update:model-value="onSearch"
        />
      </van-cell-group>

      <!-- Topic list -->
      <van-cell-group inset class="topic-list-section" v-if="filteredTopics.length > 0">
        <div
          v-for="topic in filteredTopics"
          :key="topic.id"
          class="topic-option"
          :class="{ selected: formData.topic_id === topic.id }"
          @click="selectTopic(topic)"
        >
          <div class="topic-option-info">
            <span class="topic-option-name">{{ topicDisplayName(topic) }}</span>
            <span class="topic-option-desc">{{ topicDescription(topic) }}</span>
          </div>
          <van-icon v-if="formData.topic_id === topic.id" name="success" color="var(--van-primary-color)" />
        </div>
      </van-cell-group>

      <van-cell-group inset v-else-if="searchQuery">
        <div class="no-topics">{{ t('learning.noTopicsFound') }}</div>
      </van-cell-group>

      <!-- Due date -->
      <van-cell-group inset class="date-section">
        <van-field
          v-model="dueDateDisplay"
          is-link
          readonly
          :label="t('learning.dueDate')"
          :placeholder="t('learning.dueDateOptional')"
          @click="showDatePicker = true"
        />
      </van-cell-group>

      <!-- Priority -->
      <van-cell-group inset class="priority-section">
        <van-cell :title="t('learning.priority')">
          <template #value>
            <van-radio-group v-model="formData.priority" direction="horizontal">
              <van-radio :name="0">{{ t('learning.priorityNormal') }}</van-radio>
              <van-radio :name="1">{{ t('learning.priorityHigh') }}</van-radio>
            </van-radio-group>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Submit button -->
      <div class="submit-section">
        <van-button
          type="primary"
          block
          :loading="submitting"
          :disabled="!canSubmit"
          @click="onSubmit"
        >
          {{ t('learning.submitAssignment') }}
        </van-button>
      </div>
    </van-form>

    <!-- Child picker popup -->
    <van-popup v-model:show="showChildPicker" position="bottom" round>
      <van-picker
        :columns="childColumns"
        @confirm="onChildConfirm"
        @cancel="showChildPicker = false"
      />
    </van-popup>

    <!-- Date picker popup -->
    <van-popup v-model:show="showDatePicker" position="bottom" round>
      <van-date-picker
        v-model="selectedDate"
        :title="t('learning.selectDueDate')"
        :min-date="minDate"
        @confirm="onDateConfirm"
        @cancel="showDatePicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LearningAssign' })

import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLocalizedTopic } from '@/composables/useLocalizedTopic'
import { showSuccessToast, showFailToast } from 'vant'
import { usePageLoading } from '@/composables/usePageLoading'
import { useFamilyStore } from '@/stores/family'
import { createAssignment, searchTopics } from '@/api/learning'
import type { TopicResponse } from '@/api/learning'
import PageHeader from '@/components/common/PageHeader.vue'

const { t, locale } = useI18n()
const { topicDisplayName, topicDescription } = useLocalizedTopic()
const route = useRoute()
const router = useRouter()
const familyStore = useFamilyStore()
const { increment, decrement } = usePageLoading()

const childIdFromQuery = route.query.child_id as string | undefined

const formData = ref({
  child_id: childIdFromQuery || '',
  topic_id: '',
  due_date: '',
  priority: 0,
})

const formRules = {
  child_id: [{ required: true, message: t('learning.childRequired') }],
  topic_id: [{ required: true, message: t('learning.topicRequired') }],
}

const searchQuery = ref('')
const filteredTopics = ref<TopicResponse[]>([])
const searching = ref(false)
const submitting = ref(false)
const showChildPicker = ref(false)
const showDatePicker = ref(false)
const selectedDate = ref<string[]>([])

const minDate = new Date()

const childMembers = computed(() => familyStore.members.filter(m => m.role === 'child'))

const selectedChildName = computed(() => {
  if (!formData.value.child_id) return ''
  const child = childMembers.value.find(m => String(m.id) === formData.value.child_id)
  return child?.display_name || ''
})

const childColumns = computed(() =>
  childMembers.value.map(m => ({
    text: m.display_name || m.username || '',
    value: String(m.id),
  }))
)

const dueDateDisplay = computed(() => {
  if (!formData.value.due_date) return ''
  const date = new Date(formData.value.due_date)
  return date.toLocaleDateString(locale.value)
})

const canSubmit = computed(() => formData.value.child_id && formData.value.topic_id)

let searchTimer: ReturnType<typeof setTimeout> | null = null

function onSearch(query: string) {
  if (searchTimer) clearTimeout(searchTimer)
  if (!query.trim()) {
    filteredTopics.value = []
    return
  }
  searchTimer = setTimeout(async () => {
    searching.value = true
    try {
      filteredTopics.value = await searchTopics(query.trim())
    } catch {
      filteredTopics.value = []
    } finally {
      searching.value = false
    }
  }, 300)
}

function selectTopic(topic: { id: string }) {
  formData.value.topic_id = topic.id
}

function onChildConfirm({ selectedValues }: { selectedValues: string[] }) {
  if (selectedValues[0]) {
    formData.value.child_id = selectedValues[0]
  }
  showChildPicker.value = false
}

function onDateConfirm({ selectedValues }: { selectedValues: string[] }) {
  if (selectedValues.length === 3) {
    formData.value.due_date = `${selectedValues[0]}-${selectedValues[1]}-${selectedValues[2]}`
  }
  showDatePicker.value = false
}

async function onSubmit() {
  if (!formData.value.child_id || !formData.value.topic_id) return

  submitting.value = true
  try {
    await createAssignment({
      child_id: formData.value.child_id,
      topic_id: formData.value.topic_id,
      due_date: formData.value.due_date || undefined,
      priority: formData.value.priority,
    })
    showSuccessToast(t('learning.assignmentCreated'))
    router.back()
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  increment()
  await familyStore.fetchFamily()
  decrement()
})
</script>

<style scoped>
.learning-assign-page {
  min-height: 100vh;
  padding-bottom: 20px;
}

.assign-form {
  margin-top: 12px;
}

.topic-section,
.date-section,
.priority-section {
  margin-top: 12px;
}

.topic-list-section {
  margin-top: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.topic-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--separator, #f5f5f5);
  cursor: pointer;
  transition: background 0.15s;
}

.topic-option:last-child {
  border-bottom: none;
}

.topic-option:active {
  background: var(--bg-secondary, #f5f5f5);
}

.topic-option.selected {
  background: rgba(var(--van-primary-color-rgb, 25, 137, 250), 0.08);
}

.topic-option-info {
  flex: 1;
  min-width: 0;
  margin-right: 12px;
}

.topic-option-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.topic-option-desc {
  font-size: 12px;
  color: var(--text-secondary);
  display: block;
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.no-topics {
  padding: 24px 16px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 14px;
}

.submit-section {
  padding: 24px 16px;
}
</style>
