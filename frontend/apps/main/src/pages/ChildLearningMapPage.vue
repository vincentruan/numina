<template>
  <div class="child-learning-map-page">
    <PageHeader :title="t('learning.childMap', { name: childName })" />

    <van-skeleton v-if="loading && mapItems.length === 0" :rows="5" :round="true" />

    <template v-else>
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <!-- Empty state -->
        <EmptyState v-if="mapItems.length === 0" :description="t('learning.noProgress')" />

        <template v-else>
          <!-- Subject tabs -->
          <van-tabs v-model:active="activeSubjectIdx" scrollable class="subject-tabs">
            <van-tab v-for="tab in subjectTabs" :key="tab.subject" :title="`${tab.subject} (${tab.count})`" />
          </van-tabs>

          <!-- Domain groups -->
          <div class="map-content">
            <div
              v-for="group in domainGroups"
              :key="group.domain"
              class="domain-group"
            >
              <div class="domain-group-header">
                <span class="domain-name">{{ group.domain || t('learning.ungrouped') }}</span>
                <span class="domain-count">{{ group.items.length }}</span>
              </div>
              <div class="topic-list">
                <div
                  v-for="item in group.items"
                  :key="item.id"
                  class="topic-item"
                  :class="`mastery-${item.mastery_level}`"
                >
                  <div class="topic-info">
                    <span class="topic-name">{{ topicDisplayName(item.topic) }}</span>
                    <span class="topic-desc">{{ topicDescription(item.topic) }}</span>
                  </div>
                  <van-button
                    v-if="shouldShowTranslate(item.topic)"
                    :loading="translatingIds.has(item.topic.id)"
                    :loading-text="t('learning.translating')"
                    size="small"
                    type="primary"
                    plain
                    @click="handleTranslate(item.topic.id)"
                  >
                    {{ item.topic.name_zh ? t('learning.retranslate') : t('learning.translate') }}
                  </van-button>
                  <div class="topic-mastery">
                    <van-tag :type="masteryTagType(item.mastery_level)">
                      {{ masteryLabel(item.mastery_level) }}
                    </van-tag>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </van-pull-refresh>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ChildLearningMap' })

import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLocalizedTopic } from '@/composables/useLocalizedTopic'
import { showFailToast, showSuccessToast } from 'vant'
import { usePageLoading } from '@/composables/usePageLoading'
import {
  getChildMap,
  getTopicsBatch,
  translateTopic,
  type ProgressResponse,
  type TopicResponse,
  type ProgressWithTopic,
} from '@/api/learning'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { hasChineseChars } from '@numina/shared'

const { t, locale } = useI18n()
const { topicDisplayName, topicDescription } = useLocalizedTopic()
const route = useRoute()
const { increment, decrement } = usePageLoading()

const childId = route.params.childId as string
const childName = ref('')

const loading = ref(true)
const refreshing = ref(false)
const activeSubjectIdx = ref(0)
const progressList = ref<ProgressResponse[]>([])
const topicMap = ref<Map<string, TopicResponse>>(new Map())
const translatingIds = ref<Set<string>>(new Set())

// Composite items: progress + topic
const mapItems = computed<ProgressWithTopic[]>(() =>
  progressList.value
    .filter((p) => topicMap.value.has(p.topic_id))
    .map((p) => ({
      ...p,
      topic: topicMap.value.get(p.topic_id)!,
    })),
)

// Subject tabs derived from items
const subjectTabs = computed(() => {
  const counts = new Map<string, number>()
  for (const item of mapItems.value) {
    const s = item.topic.subject
    counts.set(s, (counts.get(s) || 0) + 1)
  }
  return Array.from(counts.entries())
    .filter(([, count]) => count > 0)
    .map(([subject, count]) => ({ subject, count }))
    .sort((a, b) => a.subject.localeCompare(b.subject))
})

const selectedSubject = computed(() => subjectTabs.value[activeSubjectIdx.value]?.subject || '')

const filteredItems = computed(() =>
  mapItems.value.filter((item) => item.topic.subject === selectedSubject.value),
)

// Group by domain
const domainGroups = computed(() => {
  const groups = new Map<string, ProgressWithTopic[]>()
  for (const item of filteredItems.value) {
    const domain = item.topic.domain || ''
    if (!groups.has(domain)) {
      groups.set(domain, [])
    }
    groups.get(domain)!.push(item)
  }
  return Array.from(groups.entries())
    .map(([domain, items]) => ({ domain, items }))
    .sort((a, b) => a.domain.localeCompare(b.domain))
})

function masteryTagType(level: string): 'primary' | 'success' | 'warning' | 'danger' | 'default' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'default'> = {
    mastered: 'success',
    learning: 'primary',
    parent_review: 'warning',
    available: 'default',
    locked: 'default',
  }
  return map[level] ?? 'default'
}

function masteryLabel(level: string): string {
  const map: Record<string, string> = {
    mastered: t('learning.mastered'),
    learning: t('learning.learning'),
    parent_review: t('learning.pendingReview'),
    available: t('learning.available'),
    locked: t('learning.locked'),
  }
  return map[level] ?? level
}

function shouldShowTranslate(topic: TopicResponse): boolean {
  if (locale.value !== 'zh-CN') return false
  if (hasChineseChars(topic.name)) return false
  return true
}

async function handleTranslate(topicId: string) {
  translatingIds.value.add(topicId)
  try {
    await translateTopic(topicId)
    showSuccessToast(t('learning.translationComplete'))
    // Re-fetch this topic's details to pick up translated fields
    const updated = await getTopicsBatch([topicId])
    if (updated.length > 0) {
      const newMap = new Map(topicMap.value)
      newMap.set(topicId, updated[0])
      topicMap.value = newMap
    }
  } catch {
    showFailToast(t('learning.translationFailed'))
  } finally {
    translatingIds.value.delete(topicId)
  }
}

async function load() {
  loading.value = true
  try {
    const progress = await getChildMap(childId)
    progressList.value = progress

    // Fetch topic details in batch (single request instead of N+1)
    const uniqueTopicIds = [...new Set(progress.map((p) => p.topic_id))]
    const topicDetails = uniqueTopicIds.length > 0
      ? await getTopicsBatch(uniqueTopicIds)
      : []
    const newMap = new Map<string, TopicResponse>()
    for (const topic of topicDetails) {
      newMap.set(topic.id, topic)
    }
    topicMap.value = newMap
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    loading.value = false
  }
}

async function onRefresh() {
  await load()
  refreshing.value = false
}

onMounted(async () => {
  increment()
  // Get child name from route query or use ID as fallback
  childName.value = (route.query.name as string) || childId
  await load()
  decrement()
})
</script>

<style scoped>
.child-learning-map-page {
  min-height: 100vh;
  padding-bottom: 20px;
}

.subject-tabs {
  margin-top: 12px;
}

.map-content {
  padding: 12px;
}

.domain-group {
  margin-bottom: 16px;
}

.domain-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--bg-secondary, #f5f5f5);
  border-radius: 8px;
  margin-bottom: 8px;
}

.domain-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.domain-count {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--card-bg);
  padding: 2px 8px;
  border-radius: 10px;
}

.topic-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.topic-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  gap: 8px;
  background: var(--card-bg);
  border-radius: 10px;
  box-shadow: var(--shadow-elevated, 0 2px 8px rgba(1, 1, 32, 0.06));
}

.topic-item.mastery-locked {
  opacity: 0.5;
}

.topic-info {
  flex: 1;
  min-width: 0;
  margin-right: 12px;
}

.topic-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.topic-desc {
  font-size: 12px;
  color: var(--text-secondary);
  display: block;
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.topic-mastery {
  flex-shrink: 0;
}
</style>
