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

      <!-- Selected topic summary -->
      <van-cell-group inset class="topic-section">
        <van-cell
          :title="t('learning.selectedTopic')"
          :value="selectedTopicDisplay || t('learning.topicPicker')"
          is-link
          @click="showTopicPicker = true"
        />
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

    <!-- Topic picker popup (index bar + search) -->
    <van-popup
      v-model:show="showTopicPicker"
      position="bottom"
      round
      :style="{ height: '80vh' }"
    >
      <div class="topic-picker">
        <!-- Search bar -->
        <van-search
          v-model="searchQuery"
          :placeholder="t('learning.topicSearchPlaceholder')"
          shape="round"
          @update:model-value="onSearch"
          @focus="searchFocused = true"
        />

        <!-- Search results mode -->
        <template v-if="searchFocused && searchQuery.trim()">
          <div class="search-results">
            <div v-if="searchResults.length === 0 && !searching" class="search-empty">
              {{ t('learning.noTopicsFound') }}
            </div>
            <van-loading v-else-if="searching" class="search-loading" />
            <template v-else>
              <div
                v-for="topic in searchResults"
                :key="topic.id"
                class="search-result-item"
                :class="{ selected: formData.topic_id === topic.id }"
                @click="selectTopicFromSearch(topic)"
              >
                <div class="search-result-info">
                  <span class="search-result-name">{{ topicIndexName(topic) }}</span>
                  <span class="search-result-domain">{{ subjectLabel(topic.subject) }} · {{ topic.domain }}</span>
                </div>
                <van-icon
                  v-if="formData.topic_id === topic.id"
                  name="success"
                  color="var(--van-primary-color)"
                />
              </div>
            </template>
          </div>
        </template>

        <!-- Browse mode: subject tabs + index bar -->
        <template v-else>
          <van-tabs
            v-model:active="activeSubjectIndex"
            shrink
            sticky
          >
            <van-tab
              v-for="subj in subjectList"
              :key="subj.key"
              :title="subj.label"
            />
          </van-tabs>

          <van-index-bar
            v-if="currentDomains.length > 0"
            :index-list="domainIndexList"
            sticky
            highlight
            class="topic-index-bar"
          >
            <template v-for="group in currentDomains" :key="group.domain">
              <van-index-anchor :index="group.anchor" />
              <van-cell-group inset :title="group.domain">
                <div
                  v-for="topic in group.topics"
                  :key="topic.id"
                  class="topic-item"
                  :class="{ selected: formData.topic_id === topic.id }"
                  @click="selectTopicFromIndex(topic)"
                >
                  <span class="topic-item-name">{{ topicIndexName(topic) }}</span>
                  <van-icon
                    v-if="formData.topic_id === topic.id"
                    name="success"
                    color="var(--van-primary-color)"
                  />
                </div>
              </van-cell-group>
            </template>
          </van-index-bar>

          <div v-else-if="loadingTopics" class="topics-loading">
            <van-loading />
          </div>
          <div v-else class="topics-empty">
            {{ t('learning.noTopicsInDomain') }}
          </div>
        </template>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LearningAssign' })

import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { usePageLoading } from '@/composables/usePageLoading'
import { useFamilyStore } from '@/stores/family'
import { createAssignment, searchTopics, getTopicIndex } from '@/api/learning'
import type { TopicIndexItem } from '@/api/learning'
import PageHeader from '@/components/common/PageHeader.vue'

const { t, locale } = useI18n()

/** Display name for TopicIndexItem (no description field, so can't use useLocalizedTopic directly). */
function topicIndexName(topic: TopicIndexItem): string {
  if (locale.value.startsWith('zh') && topic.name_zh) return topic.name_zh
  return topic.name || topic.id
}
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

const submitting = ref(false)
const showChildPicker = ref(false)
const showDatePicker = ref(false)
const showTopicPicker = ref(false)
const selectedDate = ref<string[]>([])
const minDate = new Date()

// Subject tabs
const SUBJECTS = [
  'mathematics', 'science', 'english', 'history',
  'personal_social', 'life_skills', 'computing', 'learning_to_learn',
] as const

const subjectList = computed(() => [
  { key: '__all__', label: t('learning.subjectAll') },
  ...SUBJECTS.map(s => ({ key: s, label: subjectLabel(s) })),
])

const activeSubjectIndex = ref(0)
const activeSubjectKey = computed(() => subjectList.value[activeSubjectIndex.value]?.key ?? '__all__')

function subjectLabel(key: string): string {
  const k = `learning.subject${key.charAt(0).toUpperCase() + key.slice(1)}` as const
  // Dynamic i18n lookup — fallback to raw key
  return t(k) !== k ? t(k) : key
}

// Index data
const allTopics = ref<TopicIndexItem[]>([])
const loadingTopics = ref(false)

interface DomainGroup {
  domain: string
  anchor: string
  topics: TopicIndexItem[]
}

const currentDomains = computed<DomainGroup[]>(() => {
  const subject = activeSubjectKey.value
  const filtered = subject === '__all__'
    ? allTopics.value
    : allTopics.value.filter(t => t.subject === subject)

  // Group by domain
  const map = new Map<string, TopicIndexItem[]>()
  for (const topic of filtered) {
    const domain = topic.domain || t('learning.ungrouped')
    const list = map.get(domain) || []
    list.push(topic)
    map.set(domain, list)
  }

  // Build groups with anchor letters
  const groups: DomainGroup[] = []
  const usedAnchors = new Set<string>()
  for (const [domain, topics] of map) {
    // Use first letter of domain (pinyin-friendly: A-Z buckets)
    const firstChar = domain.charAt(0).toUpperCase()
    let anchor = firstChar
    // Deduplicate anchors by appending suffix
    let suffix = 1
    while (usedAnchors.has(anchor)) {
      anchor = `${firstChar}${++suffix}`
    }
    usedAnchors.add(anchor)
    groups.push({ domain, anchor, topics })
  }

  // Sort by anchor
  groups.sort((a, b) => a.anchor.localeCompare(b.anchor))
  return groups
})

const domainIndexList = computed(() => currentDomains.value.map(g => g.anchor))

// Search
const searchQuery = ref('')
const searchFocused = ref(false)
const searching = ref(false)
const searchResults = ref<TopicIndexItem[]>([])
let searchTimer: ReturnType<typeof setTimeout> | null = null

function onSearch(query: string) {
  if (searchTimer) clearTimeout(searchTimer)
  if (!query.trim()) {
    searchResults.value = []
    return
  }
  searchTimer = setTimeout(async () => {
    searching.value = true
    try {
      // Reuse full search API (returns TopicResponse, but TopicIndexItem is a subset)
      searchResults.value = await searchTopics(query.trim()) as unknown as TopicIndexItem[]
    } catch {
      searchResults.value = []
    } finally {
      searching.value = false
    }
  }, 300)
}

function selectTopicFromSearch(topic: TopicIndexItem) {
  formData.value.topic_id = topic.id
  showTopicPicker.value = false
  searchQuery.value = ''
  searchFocused.value = false
}

function selectTopicFromIndex(topic: TopicIndexItem) {
  formData.value.topic_id = topic.id
  showTopicPicker.value = false
}

// Reset search state when popup closes
watch(showTopicPicker, (show) => {
  if (!show) {
    searchQuery.value = ''
    searchFocused.value = false
    searchResults.value = []
  }
})

// Selected topic display
const selectedTopicDisplay = computed(() => {
  if (!formData.value.topic_id) return ''
  const topic = allTopics.value.find(t => t.id === formData.value.topic_id)
  if (!topic) return formData.value.topic_id
  return topicIndexName(topic)
})

// Child selector
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

async function loadTopics() {
  if (allTopics.value.length > 0) return // Already loaded
  loadingTopics.value = true
  try {
    allTopics.value = await getTopicIndex()
  } catch {
    allTopics.value = []
  } finally {
    loadingTopics.value = false
  }
}

onMounted(async () => {
  increment()
  await familyStore.fetchFamily()
  // Pre-load topics in background
  loadTopics()
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

.submit-section {
  padding: 24px 16px;
}

/* Topic picker popup */
.topic-picker {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.topic-picker :deep(.van-tabs) {
  flex-shrink: 0;
}

.topic-picker :deep(.van-tabs__content) {
  display: none;
}

.topic-index-bar {
  flex: 1;
  overflow-y: auto;
}

.topic-index-bar :deep(.van-cell-group__title) {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

.topic-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--separator, #f5f5f5);
  cursor: pointer;
  transition: background 0.15s;
}

.topic-item:last-child {
  border-bottom: none;
}

.topic-item:active {
  background: var(--bg-secondary, #f5f5f5);
}

.topic-item.selected {
  background: rgba(var(--van-primary-color-rgb, 25, 137, 250), 0.08);
}

.topic-item-name {
  font-size: 14px;
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Search results */
.search-results {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.search-result-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--separator, #f5f5f5);
  cursor: pointer;
}

.search-result-item.selected {
  background: rgba(var(--van-primary-color-rgb, 25, 137, 250), 0.08);
}

.search-result-info {
  flex: 1;
  min-width: 0;
}

.search-result-name {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.search-result-domain {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.search-empty,
.topics-empty,
.topics-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 16px;
  color: var(--text-secondary);
  font-size: 14px;
}
</style>
